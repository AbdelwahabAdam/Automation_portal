"""How a request is named where it is referred to: the activity log, an email subject."""

from .models import Request


def request_label(request: Request) -> str:
    customer = request.data.get("customer_name")
    return f"طلب {request.id} — {customer}" if customer else f"طلب {request.id}"
