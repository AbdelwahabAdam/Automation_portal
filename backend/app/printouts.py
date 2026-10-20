"""PDFs the portal draws itself, for documents Daftra's API gives no file for: the receipt
(إيصال استلام), in the layout Daftra prints it, and the work order (أمر الشغل).

The templates and logo are in templates/pdf/.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates" / "pdf"
_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html"]))


class PrintoutError(Exception):
    pass


def _pdf(template: str, **values) -> bytes:
    html = _env.get_template(template).render(**values)
    try:
        # Needs the Pango library, installed in the backend's Docker image
        from weasyprint import HTML
    except (ImportError, OSError) as error:
        raise PrintoutError(f"PDF engine not available: {error}") from error
    return HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf()


def receipt(number: str, date: str, client: str, amount: str, method: str, invoice_no: str, receiver: str,
            treasury: str = "") -> bytes:
    return _pdf("receipt.html", number=number, date=date, client=client, amount=amount, method=method,
                invoice_no=invoice_no, receiver=receiver, treasury=treasury)


def work_order(number: str, title: str, start: str, delivery: str, days: int, rows: list[str],
               responsible: str, sales_person: str) -> bytes:
    """rows: the work order's details, one line each, as in its Daftra description."""
    return _pdf("work_order.html", number=number, title=title, start=start, delivery=delivery, days=days, rows=rows,
                responsible=responsible, sales_person=sales_person)
