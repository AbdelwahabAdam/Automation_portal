"""The estimate (عرض السعر) with its lines, and its PDF.

An estimate is an offer, not a sale: Daftra gives it its own numbering, records no payment against
it and posts nothing to the accounts. So there is no receipt step here and no work order — only
the document itself, made from the same order lines an invoice would be made from.

`POST /api2/estimates.json` takes the invoice's own body: `{"Invoice": {...}, "InvoiceItem": [...]}`
(Daftra accepts `Estimate` as the header key too, and merges it into `Invoice`).
Source: https://docs.daftara.dev/15115247e0 — "Add New Estimate".
"""

from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.errors import SyncError
from ...integrations import daftra
from ...integrations.daftra import DaftraError, NotFound
from .common import (TOTAL_TOLERANCE, attach_pdf, made_before_the_request, marker, money)
from .invoice import invoice_address

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


def ensure_estimate(request, items: list[dict], staff_id: int, notes: str = "") -> dict:
    """The request's estimate in Daftra, made once however often the request is approved again."""
    data = request.data
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
                "client_id": request.daftra_client_id, "date": data.get("request_date"), "draft": 0,
                "currency_code": "AED", "store_id": settings.daftra_store_id,
                "branch_id": settings.daftra_branch_id, "sales_person_id": staff_id,
                "po_number": marker(request),
                # The address this request is for, printed on the estimate
                **invoice_address(data),
                **({"order_source_id": data["order_source"]} if data.get("order_source") else {}),
            }
            if notes:
                fields["notes"] = notes
            discount = money(data.get("discount_amount"))
            if discount > 0:
                fields["adjustment_label"] = data.get("discount_label") or "خصم"
                fields["adjustment_value"] = float(-discount)
            request.save_document(
                "estimate", daftra.create("estimates.json", {"Invoice": fields, "InvoiceItem": items}))
        estimate = get_estimate(request.daftra_estimate_id)
    request.save_document("estimate", request.daftra_estimate_id, estimate.get("no") or "")

    expected, actual = money(data.get("total_amount")), money(estimate.get("summary_total"))
    if abs(expected - actual) > TOTAL_TOLERANCE:
        raise SyncError(
            f"أُنشئ عرض السعر {request.daftra_estimate_no} في دفترة لكن إجماليه {actual} لا يساوي إجمالي الطلب "
            f"{expected}. صحّح عرض السعر في دفترة أو احذفه، ثم اعتمد الطلب مرة أخرى.", from_daftra=True,
        )
    return estimate


def save_estimate_pdf(request, estimate: dict, db: Session) -> bool:
    """Attaches the estimate's PDF to the request once, so it can be shared with the customer.

    Like the invoice's: a PDF that cannot be fetched does not stop the approval, because the
    estimate exists in Daftra either way and can be printed from there.
    """
    if any(a.field == ESTIMATE_ATTACHMENT_FIELD for a in request.attachments):
        return True
    url = estimate.get("invoice_pdf_url")
    if not url:
        return False
    try:
        content = daftra.invoice_pdf(request.daftra_estimate_id, url)
    except DaftraError:
        return False
    attach_pdf(request, ESTIMATE_ATTACHMENT_FIELD, "عرض سعر", estimate, content, db)
    return True
