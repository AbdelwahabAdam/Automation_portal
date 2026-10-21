"""Access to our Daftra account: the lists the sales forms offer, and creating clients,
invoices and payments when a request is approved."""

import http.cookiejar
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from .config import settings
from .forms import EMIRATES, PAYMENT_METHODS
from .text import day_month_year, digits, squash

TIMEOUT_SECONDS = 20
CACHE_SECONDS = 15 * 60
# Daftra (or the way to it) briefly unavailable: worth asking again
RETRY_STATUSES = {502, 503, 504}

# Our payment methods as Daftra's payment method keys, as found on the account's existing payments
# (Tabby payments are recorded there as "visa" into the «مدفوعات تابي» treasury)
PAYMENT_METHOD_KEYS = dict(zip(PAYMENT_METHODS, ["bank", "cash", "GEIDEA", "visa", "_tamara", "Apple_pay"]))


class DaftraError(Exception):
    pass


class NotFound(DaftraError):
    pass


def _error_message(raw: bytes) -> str:
    """Daftra's own explanation of a refused call, e.g. which field it did not accept."""
    try:
        body = json.loads(raw)
    except ValueError:
        return raw.decode("utf-8", "replace")[:300]
    if not isinstance(body, dict):
        return str(body)[:300]
    parts = [str(body.get("message") or "")]
    for key in ("validation_errors", "errors"):
        if body.get(key):
            parts.append(json.dumps(body[key], ensure_ascii=False))
    return " — ".join(part for part in parts if part)[:500] or json.dumps(body, ensure_ascii=False)[:300]


def _call(method: str, path: str, params: dict | None = None, body: dict | list | None = None) -> dict:
    """path starts at the account's address, e.g. "/api2/invoices.json"."""
    if not settings.daftra_subdomain or not settings.daftra_api_key:
        raise DaftraError("Daftra is not configured")
    url = f"https://{settings.daftra_subdomain}.daftra.com{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Accept": "application/json", "apikey": settings.daftra_api_key}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    # A read that fails on the way (network, timeout, Daftra briefly unavailable) is tried once more;
    # a write is not, since it may have been saved even though no answer came back
    attempts = 2 if method == "GET" else 1
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code in RETRY_STATUSES and attempt < attempts:
                continue
            message = _error_message(error.read())
            raise (NotFound if error.code == 404 else DaftraError)(f"HTTP {error.code}: {message}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt < attempts:
                continue
            raise DaftraError(str(error)) from error
        except ValueError as error:
            raise DaftraError(str(error)) from error


def get(resource: str, params: dict | None = None) -> dict:
    return _call("GET", f"/api2/{resource}", params)


def create(resource: str, body: dict, params: dict | None = None) -> int:
    """Adds a record, e.g. create("invoices.json", {"Invoice": ...}), and returns its new id."""
    result = _call("POST", f"/api2/{resource}", params, body)
    if not result.get("id"):
        raise DaftraError(f"Daftra did not return an id: {json.dumps(result, ensure_ascii=False)[:300]}")
    return int(result["id"])


def post(resource: str, body: dict) -> dict:
    """An action that is not "add a record", e.g. linking a work order to an invoice."""
    return _call("POST", f"/api2/{resource}", None, body)


def update(resource: str, body: dict):
    """Changes a record, e.g. update("clients/12.json", {"Client": {...}}); Daftra changes only the fields sent."""
    _call("PUT", f"/api2/{resource}", None, body)


def update_unconfirmed(resource: str, body: dict):
    """Like update(), for an edit Daftra saves but then answers with a redirect to an HTML error
    page (a work order's CustomModel does this). Only a real refusal is raised; the caller must read
    the record back to know whether it saved."""
    try:
        _call("PUT", f"/api2/{resource}", None, body)
    except DaftraError as error:
        cause = error.__cause__
        redirected = isinstance(cause, urllib.error.HTTPError) and 300 <= cause.code < 400
        if not (redirected or isinstance(cause, ValueError)):
            raise


def read_v2(entity: str, record_id: int) -> dict:
    """One record from the read API v2, with its related data (e.g. a work order's custom_data)."""
    return _call("GET", f"/v2/api/entity/{entity}/{record_id}/3")


def invoice_pdf(invoice_id: int, pdf_url: str) -> bytes:
    """The invoice's PDF, as Daftra prints it.

    invoice_pdf_url does not return the file: its "hash" signs the visitor in to the client view
    of that invoice (a session cookie) and redirects there. The PDF is then served at
    /client/invoices/view/<id>.pdf within that session.
    """
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    try:
        opener.open(pdf_url, timeout=TIMEOUT_SECONDS).read()
        url = f"https://{settings.daftra_subdomain}.daftra.com/client/invoices/view/{invoice_id}.pdf"
        with opener.open(url, timeout=TIMEOUT_SECONDS * 3) as response:
            content = response.read()
    except (urllib.error.URLError, TimeoutError) as error:
        raise DaftraError(str(error)) from error
    if not content.startswith(b"%PDF"):
        raise DaftraError("Daftra did not return a PDF for the invoice")
    return content


def local_phone(raw: str | None) -> str:
    """Reduces any way a UAE number is written to digits in local form, e.g. 0501234567."""
    number = digits(raw)
    if number.startswith("00971"):
        number = number[5:]
    elif number.startswith("971"):
        number = number[3:]
    return number if number.startswith("0") or not number else "0" + number


def _fold(text: str) -> str:
    """Ignores the spelling differences Daftra data has for the same place (ابو ظبى / أبوظبي)."""
    text = re.sub(r"\s+", "", text or "")
    for variants, letter in (("أإآ", "ا"), ("ى", "ي"), ("ة", "ه")):
        for variant in variants:
            text = text.replace(variant, letter)
    return text


EMIRATE_BY_CITY = {_fold(emirate): emirate for emirate in EMIRATES}
# Cities that are not emirates themselves
CITY_EMIRATE = {_fold("العين"): "أبوظبي"}


def address_from_daftra(client: dict) -> dict:
    """A Daftra client (or one of its addresses) as our address fields."""
    city, area = (client.get("city") or "").strip(), (client.get("state") or "").strip()
    emirate = EMIRATE_BY_CITY.get(_fold(city))
    if emirate is None:
        # Keep an unrecognised city (or العين) visible in the area instead of dropping it
        emirate = CITY_EMIRATE.get(_fold(city), "")
        area = "، ".join(part for part in (city, area) if part)
    return {
        "emirate": emirate,
        "area": area,
        "street": (client.get("address1") or "").strip(),
        "house": (client.get("address2") or "").strip(),
    }


# ---------- Lists used as drop-downs (cached, they change rarely) ----------

_cache: dict[str, tuple[float, list]] = {}
# Re-entrant: a list's loader may use another cached list (e.g. categories with their locations)
_cache_lock = threading.RLock()


def _cached(key: str, loader, seconds: int = CACHE_SECONDS) -> list:
    with _cache_lock:
        entry = _cache.get(key)
    if entry and time.monotonic() - entry[0] < seconds:
        return entry[1]
    # Loaded without holding the lock: a slow list (e.g. one reading every client) must not hold up the others
    try:
        value = loader()
    except DaftraError:
        # Daftra being down should not empty a list we already have
        if entry:
            return entry[1]
        raise
    with _cache_lock:
        _cache[key] = (time.monotonic(), value)
    return value


def _all(resource: str, model: str, workers: int = 4) -> list[dict]:
    first = get(f"{resource}.json", {"limit": 100, "page": 1})
    page_count = first.get("pagination", {}).get("page_count", 1)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rest = list(pool.map(lambda page: get(f"{resource}.json", {"limit": 100, "page": page}), range(2, page_count + 1)))
    return [row[model] for page in (first, *rest) for row in page.get("data", [])]


def list_staff_members() -> list[dict]:
    """Active Daftra staff with their ids, for linking a portal user to one."""
    def load():
        members = [
            {"id": int(member["id"]),
             "name": squash(member.get("full_name") or f"{member.get('name') or ''} {member.get('last_name') or ''}")}
            for member in _all("staff", "Staff")
            if member.get("active") == "1"
        ]
        return sorted((m for m in members if m["name"]), key=lambda m: m["name"])

    return _cached("staff_members", load)


def list_staff() -> list[str]:
    """Names of active Daftra staff, each once, for the forms' staff fields (e.g. «اسم المحصل»).
    Read from the same cached list as list_staff_members, so Daftra is asked once for both."""
    return sorted({member["name"] for member in list_staff_members()})


def list_clients() -> list[dict]:
    """Every Daftra client, raw, for the nightly job that rebuilds our local copy (app.import_clients)."""
    return _all("clients", "Client")


def list_treasuries() -> list[dict]:
    """Active treasuries and bank accounts a payment can be received into."""
    def load():
        rows = _all("treasuries", "Treasury")
        return sorted(
            ({"id": int(row["id"]), "name": squash(row.get("name"))} for row in rows if row.get("active") == "1"),
            key=lambda row: row["name"],
        )

    return _cached("treasuries", load)


def list_client_categories() -> list[dict]:
    """Daftra's client categories (a client's التصنيف, e.g. «العين العامره»). Only the read API v2 lists them."""
    def load():
        rows, page = [], 1
        while True:
            body = _call("GET", "/v2/api/entity/client_category/list/1", {"limit": 100, "page": page})
            rows += body.get("data", [])
            if page >= (body.get("last_page") or 1):
                break
            page += 1
        named = ({"id": int(row["id"]), "name": squash(row.get("name"))} for row in rows)
        return sorted((row for row in named if row["name"]), key=lambda row: row["name"])

    return _cached("client_categories", load)


# Each city as Daftra's clients write it (folded with _fold), as the form's (الإمارة, المنطقة)
CITY_LOCATIONS = {
    _fold(city): location
    for cities, location in [
        (["العين", "alain", "al ain"], ("أبوظبي", "منطقة العين")),
        (["ابو ظبى", "ابوظبى", "ابو ظبي", "أبو ظبي", "أبوظبي", "ابوظبي", "ابو طبى", "ابوطبى", "abu dhabi"], ("أبوظبي", "منطقة أبوظبي")),
        (["الظفرة", "الظفره"], ("أبوظبي", "منطقة الظفرة")),
        (["دبى", "دبي", "dubai"], ("دبي", "مدينة دبي")),
        (["حتا"], ("دبي", "حتا")),
        (["الشارقه", "الشارقة"], ("الشارقة", "مدينة الشارقة")),
        (["خورفكان"], ("الشارقة", "خورفكان")),
        (["كلباء"], ("الشارقة", "كلباء")),
        (["عجمان"], ("عجمان", "مدينة عجمان")),
        (["ام القوين", "ام القيوين", "أم القيوين"], ("أم القيوين", "مدينة أم القيوين")),
        (["راس الخيمه", "رأس الخيمة", "راس الخيمة"], ("رأس الخيمة", "نطاق مدينة رأس الخيمة")),
        (["الفجيره", "الفجيرة"], ("الفجيرة", "مدينة الفجيرة")),
    ]
    for city in cities
}


def _city_location(text: str) -> tuple[str, str] | None:
    folded = _fold(re.sub(r"[^\w\s]", " ", (text or "").lower()))
    return CITY_LOCATIONS.get(folded)


def _name_location(name: str) -> tuple[str, str] | None:
    """A category whose name holds its city, e.g. «دبي البرشاء 3» or «الزعفرانه ابو ظبى»."""
    words = (name or "").split()
    for size in (2, 1):
        for start in range(len(words) - size + 1):
            found = _city_location(" ".join(words[start:start + size]))
            if found:
                return found
    return None


CATEGORY_LOCATIONS = "client_categories_with_location"


def client_categories_with_location() -> list[dict]:
    """The client categories, each with the الإمارة and المنطقة so picking one can fill both in:
    where its clients mostly live, else the city in its name, else that of the other categories
    starting with the same word (e.g. «الشامخه 1» like «الشامخه»); None where nothing tells.
    It reads every client (over a minute), so it is kept for hours and warmed at startup."""
    def load():
        votes: dict[int, Counter] = defaultdict(Counter)
        for client in _all("clients", "Client", workers=8):
            location = _city_location(client.get("city") or "")
            if client.get("category_id") and location:
                votes[int(client["category_id"])][location] += 1
        categories = list_client_categories()
        found = {}
        for category in categories:
            counted = votes.get(category["id"])
            found[category["id"]] = counted.most_common(1)[0][0] if counted else _name_location(category["name"])
        by_first_word: dict[str, Counter] = defaultdict(Counter)
        for category in categories:
            if found[category["id"]] and category["name"].split():
                by_first_word[_fold(category["name"].split()[0])][found[category["id"]]] += 1
        rows = []
        for category in categories:
            location = found[category["id"]]
            if location is None and category["name"].split():
                same = by_first_word.get(_fold(category["name"].split()[0]))
                location = same.most_common(1)[0][0] if same else None
            rows.append({**category, "emirate": location[0] if location else None, "area": location[1] if location else None})
        return rows

    return _cached(CATEGORY_LOCATIONS, load, seconds=6 * 60 * 60)


def client_category(client_id: int) -> dict | None:
    """The client's current category as {"id", "name"}, or None if it has none."""
    row = get(f"clients/{client_id}.json").get("data", {}).get("Client", {})
    if not row.get("category_id"):
        return None
    return {"id": int(row["category_id"]), "name": squash(row.get("category"))}


def open_invoices(client_id: int) -> list[dict]:
    """The client's issued invoices that still have something to pay, newest first."""
    rows = get("invoices.json", {"client_id": client_id, "limit": 100}).get("data", [])
    found = []
    for row in rows:
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


def list_order_sources() -> list[dict]:
    """Active order sources (an invoice's مصدر الطلب). Only the read API v2 lists them."""
    def load():
        body = _call("GET", "/v2/api/entity/order_source/list/1", {"limit": 100})
        rows = body.get("data", [])
        return [
            {"id": int(row["id"]), "name": squash(row.get("name"))}
            for row in sorted(rows, key=lambda row: row.get("display_order") or 0)
            if row.get("status") == 1
        ]

    return _cached("order_sources", load)
