"""PDFs the portal draws itself, for documents Daftra's API gives no file for: the receipt
(إيصال استلام), in the layout Daftra prints it, the work order (أمر الشغل), and the estimate
(عرض سعر), whose link from Daftra does not open (checked on the live account 2026-11-14).

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


def work_order(number: str, title: str, start: str, delivery: str, rows: list[str], values: dict,
               client_name: str, client_code: str, phone: str, address: str, location_url: str,
               coordinates: str, product_image: str, invoice_no: str, responsible: str, sales_person: str,
               days: str = "", device: str = "") -> bytes:
    """rows: the work order's details, one line each, printed under «الوصف».
    values: the work order's custom fields by their own names (work_order.work_order_values).
    days: مدة التركيب; device: نوع الجهاز, which the title alone stands in for when there is none."""
    return _pdf("work_order.html", number=number, title=title, start=start, delivery=delivery, rows=rows,
                values=values, client_name=client_name, client_code=client_code, phone=phone, address=address,
                location_url=location_url, coordinates=coordinates, product_image=product_image,
                invoice_no=invoice_no, responsible=responsible, sales_person=sales_person,
                days=days, device=device)


def estimate(number: str, date: str, client_name: str, client_code: str, phone: str, address: str,
             sales_person: str, lines: list[dict], subtotal: str, adjustment_label: str, adjustment: str,
             total: str, taxes: list[dict], notes: list[str], terms: list[str]) -> bytes:
    """lines: {name, description, unit_price, quantity, total}, as Daftra holds them, amounts written out.
    adjustment: the discount, signed (-1,500.00); empty when there is none.
    taxes: {label, amount, included}; an included one is printed under the total, as part of it.
    notes, terms: one line each; an empty line in terms is a gap between paragraphs."""
    return _pdf("estimate.html", number=number, date=date, client_name=client_name, client_code=client_code,
                phone=phone, address=address, sales_person=sales_person, lines=lines, subtotal=subtotal,
                adjustment_label=adjustment_label, adjustment=adjustment, total=total, taxes=taxes, notes=notes,
                terms=terms)
