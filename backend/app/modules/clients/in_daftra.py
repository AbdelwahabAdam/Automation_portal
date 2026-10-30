"""The customer as Daftra holds it: reading a Daftra client into our fields, and what we read back.

This is our knowledge of our own data, not Daftra's API, which is why it does not live in
`integrations/daftra`: the city spellings are the ones our account's clients were typed with,
and the emirate and area are the forms' own choices.
"""

import re
from collections import Counter, defaultdict

from ...core.text import day_month_year, fold_arabic
from ...integrations import daftra

# Each city as Daftra's clients write it (folded with fold_arabic), as the form's (الإمارة, المنطقة)
CITY_LOCATIONS = {
    fold_arabic(city): location
    for cities, location in [
        (["العين", "alain", "al ain"], ("أبوظبي", "منطقة العين")),
        (["ابو ظبى", "ابوظبى", "ابو ظبي", "أبو ظبي", "أبوظبي", "ابوظبي", "ابو طبى", "ابوطبى", "abu dhabi"],
         ("أبوظبي", "منطقة أبوظبي")),
        (["الظفرة", "الظفره"], ("أبوظبي", "منطقة الظفرة")),
        (["دبى", "دبي", "dubai"], ("دبي", "مدينة دبي")),
        (["حتا", "hatta"], ("دبي", "حتا")),
        (["الشارقه", "الشارقة", "sharjah"], ("الشارقة", "مدينة الشارقة")),
        (["خورفكان", "khorfakkan"], ("الشارقة", "خورفكان")),
        (["كلباء", "kalba"], ("الشارقة", "كلباء")),
        (["عجمان", "ajman"], ("عجمان", "مدينة عجمان")),
        (["ام القوين", "ام القيوين", "أم القيوين", "umm al quwain"], ("أم القيوين", "مدينة أم القيوين")),
        (["راس الخيمه", "رأس الخيمة", "راس الخيمة", "ras al khaimah"], ("رأس الخيمة", "نطاق مدينة رأس الخيمة")),
        (["الفجيره", "الفجيرة", "fujairah"], ("الفجيرة", "مدينة الفجيرة")),
    ]
    for city in cities
}


def city_location(text: str) -> tuple[str, str] | None:
    folded = fold_arabic(re.sub(r"[^\w\s]", " ", (text or "").lower()))
    return CITY_LOCATIONS.get(folded)


def _name_location(name: str) -> tuple[str, str] | None:
    """A category whose name holds its city, e.g. «دبي البرشاء 3» or «الزعفرانه ابو ظبى»."""
    words = (name or "").split()
    for size in (2, 1):
        for start in range(len(words) - size + 1):
            found = city_location(" ".join(words[start:start + size]))
            if found:
                return found
    return None


def address_from_daftra(client: dict) -> dict:
    """A Daftra client (or one of its addresses) as our address fields.

    The emirate comes from CITY_LOCATIONS, which knows the spellings Daftra's data uses for the
    same place — «دبى», «دبي», «Dubai» — and the cities that are not emirates (العين, حتا).
    The area keeps the neighbourhood Daftra holds («الخوانيج 2»), which is what the installation
    team needs on the work order; it is not one of the regions the form lists.
    """
    city, area = (client.get("city") or "").strip(), (client.get("state") or "").strip()
    found = city_location(city)
    if found:
        # With no neighbourhood of its own, the city's own region says where it is («العين» is
        # not أبوظبي the city), and that one the form does offer
        emirate, area = found[0], area or found[1]
    elif city_location(area):
        # The two are the other way round on some clients: «السمحه» as the city, «ابو ظبي» as the area
        emirate, area = city_location(area)[0], city
    else:
        # Keep an unrecognised city visible in the area instead of dropping it
        emirate = ""
        area = "، ".join(part for part in (city, area) if part)
    return {
        "emirate": emirate,
        "area": area,
        "street": (client.get("address1") or "").strip(),
        "house": (client.get("address2") or "").strip(),
    }


CATEGORY_LOCATIONS = "client_categories_with_location"


def categories_with_location() -> list[dict]:
    """The client categories, each with the الإمارة and المنطقة so picking one can fill both in:
    where its clients mostly live, else the city in its name, else that of the other categories
    starting with the same word (e.g. «الشامخه 1» like «الشامخه»); None where nothing tells.
    It reads every client (over a minute), so it is kept for hours and warmed at startup."""
    def load():
        votes: dict[int, Counter] = defaultdict(Counter)
        for client in daftra.all_records("clients", "Client", workers=8):
            location = city_location(client.get("city") or "")
            if client.get("category_id") and location:
                votes[int(client["category_id"])][location] += 1
        categories = daftra.list_client_categories()
        found = {}
        for category in categories:
            counted = votes.get(category["id"])
            found[category["id"]] = counted.most_common(1)[0][0] if counted else _name_location(category["name"])
        by_first_word: dict[str, Counter] = defaultdict(Counter)
        for category in categories:
            if found[category["id"]] and category["name"].split():
                by_first_word[fold_arabic(category["name"].split()[0])][found[category["id"]]] += 1
        rows = []
        for category in categories:
            location = found[category["id"]]
            if location is None and category["name"].split():
                same = by_first_word.get(fold_arabic(category["name"].split()[0]))
                location = same.most_common(1)[0][0] if same else None
            rows.append({**category, "emirate": location[0] if location else None,
                         "area": location[1] if location else None})
        return rows

    return daftra.cached(CATEGORY_LOCATIONS, load, seconds=6 * 60 * 60)


def open_invoices(client_id: int) -> list[dict]:
    """The client's issued invoices that still have something to pay, newest first."""
    found = []
    for row in daftra.client_invoices(client_id):
        invoice = row["Invoice"]
        unpaid = float(invoice.get("summary_unpaid") or 0)
        if invoice.get("draft") == "0" and unpaid > 0.005:
            # The list gives 2026-10-19; Daftra prints 19/10/2026
            day = day_month_year(invoice.get("date") or "")
            found.append({"id": int(invoice["id"]), "no": invoice.get("no") or "", "date": day,
                          "total": float(invoice.get("summary_total") or 0), "unpaid": round(unpaid, 2)})
    return sorted(found, key=lambda invoice: invoice["id"], reverse=True)


def invoice_label(invoice: dict) -> str:
    """How an open invoice reads in the balance-payment form, e.g. «06273 — 18/10/2026 — المتبقي 4,650 درهم»."""
    return f"{invoice['no']} — {invoice['date']} — المتبقي {invoice['unpaid']:,.2f}".removesuffix(".00") + " درهم"
