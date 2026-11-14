"""The estimate (عرض السعر) with its lines, and its PDF.

An estimate is an offer, not a sale: Daftra gives it its own numbering, records no payment against
it and posts nothing to the accounts. So there is no receipt step here and no work order — only
the document itself, made from the same order lines an invoice would be made from.

`POST /api2/estimates.json` takes the invoice's own body: `{"Invoice": {...}, "InvoiceItem": [...]}`
(Daftra accepts `Estimate` as the header key too, and merges it into `Invoice`).
Source: https://docs.daftara.dev/15115247e0 — "Add New Estimate".
"""

import html
import re
from decimal import Decimal

from sqlalchemy.orm import Session

from . import printouts
from ...core.config import settings
from ...core.errors import SyncError
from ...core.text import day_month_year, squash
from ...integrations import daftra
from ...integrations.daftra import NotFound
from .common import (TOTAL_TOLERANCE, attach_pdf, made_before_the_request, marker, money, printed_terms,
                     sales_person_name)
from .documents import Estimate
from .work_order import full_address

# The field the estimate's PDF is attached to the request under (not a field of any form)
ESTIMATE_ATTACHMENT_FIELD = "daftra_estimate"


def get_estimate(estimate_id: int) -> dict:
    return daftra.get(f"estimates/{estimate_id}.json")["data"]["Estimate"]


def find_estimate(request) -> int | None:
    """The estimate this request already made, if the last approval got that far.

    Found the way the invoice is, by the mark in po_number. Daftra documents no po_number on an
    estimate's create, so an account that drops it leaves nothing to find: the id kept on the
    request is what carries a retry, and this only has to answer when that id was lost.
    """
    rows = daftra.get("estimates.json", {"client_id": request.daftra_client_id, "limit": 100}).get("data", [])
    return next((int(row["Estimate"]["id"]) for row in rows
                 if row["Estimate"].get("po_number") == marker(request)
                 and not made_before_the_request(request, row["Estimate"].get("created"))), None)


def make_estimate(request, doc: Estimate) -> dict:
    """The request's estimate in Daftra, made once however often the request is approved again."""
    estimate = None
    if request.daftra_estimate_id is not None:
        try:
            estimate = get_estimate(request.daftra_estimate_id)
            # Not this request's own: another portal's mark, or older than the request itself
            if ((estimate.get("po_number") or "") != marker(request)
                    or made_before_the_request(request, estimate.get("created"))):
                estimate = None
                raise NotFound("not this request's estimate")
        except NotFound:
            # Deleted in Daftra since, so it is made again
            request.forget_document("estimate")
    if estimate is None:
        request.save_document("estimate", find_estimate(request))
        if request.daftra_estimate_id is None:
            fields = {
                # is_offline: the estimate is printed and handed over, not emailed by Daftra.
                # Without it the account's own setting applies, and Daftra refuses to save an
                # estimate for a client with no email: «البريد الإلكتروني مطلوب إذا اخترت أن ترسل
                # الفاتورة عبر البريد». An invoice is sent the same way, for the same reason.
                "client_id": request.daftra_client_id, "date": doc.date, "draft": 0,
                "is_offline": 1,
                "currency_code": "AED", "store_id": settings.daftra_store_id,
                "branch_id": settings.daftra_branch_id, "sales_person_id": doc.sales_person,
                "po_number": marker(request),
                # أنشئ بواسطة as well as بيعت بواسطة; without it, the API key itself
                "staff_id": doc.sales_person,
                # The address this request is for, printed on the estimate
                **doc.address,
                **({"order_source_id": doc.order_source} if doc.order_source else {}),
            }
            if doc.notes:
                fields["notes"] = doc.notes
            discount = money(doc.discount)
            if discount > 0:
                fields["adjustment_label"] = doc.discount_label or "خصم"
                fields["adjustment_value"] = float(-discount)
            # Not yet seen on a real estimate: printed on an invoice's last page, and sent the same way
            term = doc.terms
            if term is not None:
                fields["html_notes"] = printed_terms.as_html(term.body)
            request.save_document(
                "estimate", daftra.create("estimates.json", {"Invoice": fields, "InvoiceItem": list(doc.items)}))
            request.printed_terms_id, request.printed_terms = (term.id, term.label) if term else (None, None)
        estimate = get_estimate(request.daftra_estimate_id)
    request.save_document("estimate", request.daftra_estimate_id, estimate.get("no") or "")

    expected, actual = money(doc.total), money(estimate.get("summary_total"))
    if abs(expected - actual) > TOTAL_TOLERANCE:
        raise SyncError(
            f"أُنشئ عرض السعر {request.daftra_estimate_no} في دفترة لكن إجماليه {actual} لا يساوي إجمالي الطلب "
            f"{expected}. صحّح عرض السعر في دفترة أو احذفه، ثم اعتمد الطلب مرة أخرى.", from_daftra=True,
        )
    return estimate


def save_estimate_pdf(request, estimate: dict, db: Session) -> bool:
    """Attaches the estimate's PDF to the request once, so it can be shared with the customer.

    The portal draws it (draw_estimate): the PDF link Daftra gives an estimate does not open —
    unlike an invoice's, its hash signs nobody in — and the API key cannot download one either
    (both checked on the live account, estimate 00347, 2026-11-14). Like the invoice's, a PDF that
    cannot be made does not stop the approval: the estimate exists in Daftra either way.
    """
    if any(a.field == ESTIMATE_ATTACHMENT_FIELD for a in request.attachments):
        return True
    try:
        content = draw_estimate(request, estimate)
    except printouts.PrintoutError:
        return False
    attach_pdf(request, ESTIMATE_ATTACHMENT_FIELD, "عرض سعر", estimate, content, db)
    return True


def draw_estimate(request, estimate: dict) -> bytes:
    """The عرض سعر PDF, from the estimate as Daftra holds it: its number, its lines, its discount, VAT
    and total are Daftra's own, so the PDF says what Daftra says. Who it is for and the address are
    the request's, as the work order prints them.

    Kept apart from saving it so app.jobs estimate_pdfs can draw one again, or for an estimate
    approved before the portal drew them.
    """
    data = request.data
    items = estimate_items(estimate)
    totals = [money(item.get("unit_price")) * Decimal(str(item.get("quantity") or 0)) for item in items]
    lines = [{
        "name": str(item.get("item") or ""),
        "name_ltr": left_to_right(item.get("item")),
        "description": squash(item.get("description")),
        "description_ltr": left_to_right(item.get("description")),
        "unit_price": amount(item.get("unit_price")),
        "quantity": quantity(item.get("quantity")),
        "total": amount(total),
    } for item, total in zip(items, totals)]
    # The discount, as Daftra holds it: a negative adjustment
    adjustment = money(estimate.get("adjustment_value"))
    client = estimate.get("Client") or {}
    return printouts.estimate(
        number=str(estimate.get("no") or request.daftra_estimate_no or ""),
        date=day_month_year(str(estimate.get("original_date") or estimate.get("date") or "")),
        client_name=squash(data.get("customer_name")) or str(estimate.get("client_business_name") or ""),
        client_code=str(client.get("client_number") or data.get("client_code") or ""),
        phone=str(data.get("phone") or estimate.get("client_phone1") or ""),
        address=full_address(data),
        sales_person=sales_person_name(request),
        lines=lines,
        subtotal=amount(sum(totals, Decimal(0))),
        adjustment_label=str(estimate.get("adjustment_label") or "خصم"),
        adjustment=amount(adjustment) if adjustment else "",
        total=amount(estimate.get("summary_total")),
        taxes=taxes(estimate),
        notes=[line for line in str(estimate.get("notes") or "").splitlines() if line.strip()],
        terms=html_lines(str(estimate.get("html_notes") or "")),
    )


def estimate_items(estimate: dict) -> list[dict]:
    """Its lines in Daftra's order: InvoiceItem, as Daftra returns an estimate."""
    return sorted(estimate.get("InvoiceItem") or [], key=lambda item: int(item.get("display_order") or 0))


def taxes(estimate: dict) -> list[dict]:
    """The VAT, as Daftra worked it out: {label, amount, included}. The account's is included in the price."""
    found = estimate.get("InvoiceTax") or {}
    rows = found.values() if isinstance(found, dict) else found
    out = []
    for tax in rows:
        rate = Decimal(str(tax.get("value") or 0)).normalize()
        included = str(tax.get("included") or "") == "1"
        label = ("شامل " if included else "") + f"ضريبة القيمة المضافة {rate:f}%"
        out.append({"label": label, "amount": amount(tax.get("invoice_value")), "included": included})
    return out


def left_to_right(text) -> bool:
    """Written in English: its first letter is Latin. The PDF engine does not work a paragraph's
    direction out for itself, so «2-Wolf water cooler» would print as «Wolf water cooler-2»."""
    first = re.search("[A-Za-z؀-ۿ]", str(text or ""))
    return bool(first) and first[0].isascii()


def amount(value) -> str:
    """8450 as 8,450.00."""
    return f"{money(value):,.2f}"


def quantity(value) -> str:
    """2 as 2, and 1.5 as 1.5: Daftra keeps quantities as text with decimals."""
    number = Decimal(str(value or 0)).normalize()
    return f"{number:f}"


def html_lines(markup: str) -> list[str]:
    """Daftra's html_notes (the terms) as lines of plain text; an empty paragraph is an empty line.

    Read as text rather than printed as HTML: it comes back from Daftra, where anyone can edit it."""
    text = re.sub(r"(?i)<br\s*/?>", "\n", markup)
    text = re.sub(r"(?i)</(p|div|li|h\d)\s*>", "\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    lines = []
    for line in (part.strip() for part in text.splitlines()):
        if line or (lines and lines[-1]):
            lines.append(line)
    while lines and not lines[-1]:
        lines.pop()
    return lines
