"""A stand-in for our Daftra account, answering the same calls without a network.

Two uses, one fake:

- **Tests.** A new account per test, in memory, recording every call in `calls` as
  (method, path, params, body), so a test can check exactly what the portal would have sent.
  Ids start at 7000, which is what the payload tests were written against.
- **A local portal** (`DAFTRA_FAKE=true`). The whole flow can be tried by hand — fill a form,
  approve it, open the invoice, receipt and work order, fail midway and approve again — without
  real numbered invoices on the live account. It then keeps its data in a file so a restart does
  not forget invoices that requests still point at, and its ids start at 900000001, so a fake id
  that ever reached the live account would find nothing rather than a real record.

What it knows about how Daftra behaves is the point of it, and is kept here: a client save
refused without its custom fields, the name rebuilt from the name fields, the order-source edit
that adds a copy. When the live account shows a new quirk, add it here.
"""

import json
import re
import threading
from datetime import datetime
from pathlib import Path

from ...core.text import UAE
from .errors import DaftraError, NotFound

# Ids a local fake hands out. Far above anything the live account holds, so a fake id that
# reached it would find nothing rather than a real record.
FIRST_LOCAL_ID = 900000001
# A client's رقم العميل stays six digits, because the forms check that
FIRST_LOCAL_CLIENT_NUMBER = 900001
# How many calls the file keeps, for `fake_daftra calls`
KEPT_CALLS = 500
# What the test account starts its ids at: the payload tests were written against these
FIRST_TEST_ID = 7000

# The treasuries the forms expect: TREASURY_BY_METHOD's ids, with the names the account uses
LOCAL_TREASURIES = [
    {"id": "13", "name": "ADIB NEW CURRENT", "active": "1"},
    {"id": "9", "name": "خزينه المكتب", "active": "1"},
    {"id": "16", "name": "GEIDEA POS", "active": "1"},
    {"id": "7", "name": "مدفوعات تابي", "active": "1"},
    {"id": "8", "name": "مدفوعات تمارا", "active": "1"},
    {"id": "12", "name": "مدفوعات الموقع", "active": "1"},
]


class FakeDaftra:
    """One fake Daftra account.

    `store`: where to keep it, so it survives a restart and a command can read it (a local
    portal). None keeps it in memory only, which is what a test wants.
    """

    def __init__(self, store: Path | None = None, first_id: int = FIRST_TEST_ID,
                 numbered_clients: bool = False, draws_pdfs: bool = False):
        self.store = Path(store) if store else None
        self.numbered_clients = numbered_clients
        self.draws_pdfs = draws_pdfs
        self._lock = threading.RLock()
        # Calls that were answered, and those refused by fail_once
        self.calls = []
        self.failed = []
        self.clients = {}
        self.invoices = {}
        # Offers (عروض الأسعار), kept apart from the invoices: Daftra numbers them separately
        self.estimates = {}
        self.payments = {}
        self.work_orders = {}
        # Files uploaded to the account's file store, and the next id one gets
        self.uploads = []
        self.staff = [{"id": "71", "full_name": "Sales One", "active": "1"},
                      {"id": "40", "full_name": "Manager One", "active": "1"},
                      {"id": "9", "full_name": "Old Staff", "active": "0"}]
        self.treasuries = [{"id": "13", "name": "ADIB NEW CURRENT", "active": "1"},
                           {"id": "9", "name": "خزينه المكتب", "active": "1"},
                           {"id": "99", "name": "Closed", "active": "0"}]
        self.order_sources = [{"id": 16, "name": "Sales-جديد", "status": 1, "display_order": 2},
                              {"id": 12, "name": "water", "status": 1, "display_order": 1},
                              {"id": 3, "name": "old", "status": 0, "display_order": 0}]
        # Raw Daftra products, as GET /api2/products.json lists them
        self.products = []
        self.categories = []
        self.next_id = first_id
        self.next_client_number = FIRST_LOCAL_CLIENT_NUMBER
        # Set to a path prefix (e.g. "/api2/invoice_payments.json") to make that call fail once
        self.fail_once = None
        if self.store:
            self.treasuries = [dict(row) for row in LOCAL_TREASURIES]
            self.load()

    # ---------- keeping it across restarts ----------

    KEPT = ("clients", "invoices", "estimates", "payments", "work_orders", "uploads", "staff", "treasuries",
            "order_sources", "products", "categories", "next_id", "next_client_number", "calls")

    def load(self):
        """Reads the file back, if it is there and readable. A broken file starts afresh."""
        if not self.store or not self.store.exists():
            return
        try:
            saved = json.loads(self.store.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return
        for name in self.KEPT:
            if name not in saved:
                continue
            value = saved[name]
            # JSON keys are strings; these are kept by integer id
            if name in ("clients", "invoices", "estimates", "payments", "work_orders"):
                value = {int(key): row for key, row in value.items()}
            setattr(self, name, value)

    def save(self):
        """Replaces the file whole, so a half-written one is never read back."""
        if not self.store:
            return
        self.calls = self.calls[-KEPT_CALLS:]
        body = {name: getattr(self, name) for name in self.KEPT}
        for name in ("clients", "invoices", "estimates", "payments", "work_orders"):
            body[name] = {str(key): row for key, row in body[name].items()}
        try:
            self.store.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.store.with_suffix(".writing")
            temporary.write_text(json.dumps(body, ensure_ascii=False, default=str), encoding="utf-8")
            temporary.replace(self.store)
        except OSError:
            pass          # a local convenience: never fail a request because the file would not write

    def reset(self):
        """Forgets everything; the next start seeds it again."""
        if self.store and self.store.exists():
            self.store.unlink()

    def _new_id(self):
        self.next_id += 1
        return self.next_id

    def _client_number(self, client_id: int) -> str:
        if not self.numbered_clients:
            return f"{client_id:06d}"
        number = self.next_client_number
        self.next_client_number += 1
        return f"{number:06d}"

    # ---------- what a test and the seed put in ----------

    def add_client(self, client_id, phone, name="Existing", category_id=None, client_number=None, custom=None,
                   address=None, link=""):
        # custom: the required custom fields, as a client added through the portal has them
        # address: the client's own address block (city holds the emirate, state the area)
        # link: the رابط اللوكيشن, which Daftra keeps one of per client
        self.clients[int(client_id)] = {"id": str(client_id), "business_name": name, "phone1": phone, "phone2": "",
                                        "client_number": client_number or f"{int(client_id):06d}",
                                        "category_id": str(category_id) if category_id else "", "category": "",
                                        "custom": custom, "link": link, **(address or {})}
        self.save()

    def add_invoice(self, client_id, total, paid=0.0, no=None, draft="0"):
        invoice_id = self._new_id()
        self.invoices[invoice_id] = {
            "id": str(invoice_id), "client_id": str(client_id), "no": no or f"0{invoice_id}", "draft": draft,
            "date": "2026-10-18", "po_number": "", "summary_total": str(total), "items": [], "payments": [],
            # Daftra stamps every record in the account's own time, which is the UAE's
            "created": datetime.now(UAE).strftime("%Y-%m-%d %H:%M:%S"),
            "documents": [], "initial_paid": paid,
        }
        self.save()
        return invoice_id

    def seed(self, data: dict) -> dict:
        """Adds what the local database knows and the fake has not seen: clients with their
        addresses and the custom fields our account requires, products linked to Daftra,
        categories, and the staff linked to users. Already-known records are left alone.

        Takes plain data, so nothing here reads the database: `app.fake_daftra` does that.
        """
        added = {"clients": 0, "products": 0, "categories": 0, "staff": 0}
        with self._lock:
            for client in data.get("clients", ()):
                if int(client["daftra_id"]) in self.clients:
                    continue
                self.add_client(
                    int(client["daftra_id"]), client.get("phone") or "", name=client.get("name") or "عميل",
                    category_id=client.get("category_id"), client_number=client.get("client_code"),
                    # Our account refuses a client save without these two
                    custom={"test": client.get("device_name") or "N + F",
                            "coordinates_text": client.get("coordinates") or "0,0"},
                    address=client.get("address") or {}, link=client.get("link") or "",
                )
                self.clients[int(client["daftra_id"])]["phone2"] = client.get("phone2") or ""
                added["clients"] += 1
            known_products = {str(row["id"]) for row in self.products}
            for product in data.get("products", ()):
                if str(product["daftra_id"]) in known_products:
                    continue
                self.products.append({"id": str(product["daftra_id"]), "name": product.get("name") or "",
                                      "unit_price": str(product.get("unit_price") or 0), "active": "1"})
                added["products"] += 1
            known_categories = {int(row["id"]) for row in self.categories}
            for category in data.get("categories", ()):
                if int(category["daftra_id"]) in known_categories:
                    continue
                self.categories.append({"id": int(category["daftra_id"]), "name": category.get("name") or ""})
                added["categories"] += 1
            known_staff = {str(row["id"]) for row in self.staff}
            for member in data.get("staff", ()):
                if str(member["daftra_staff_id"]) in known_staff:
                    continue
                self.staff.append({"id": str(member["daftra_staff_id"]),
                                   "full_name": member.get("name") or "", "active": "1"})
                added["staff"] += 1
            if not self.clients and not data.get("clients"):
                self._add_samples()
                added["clients"] = len(self.clients)
            self.save()
        return added

    def _add_samples(self):
        """With no local clients at all, a few to try a form against; a client sync brings in more."""
        for phone, name, city, area in (("0501234567", "عميل تجريبي أول", "دبي", "الخوانيج 2"),
                                        ("0552223344", "عميل تجريبي ثاني", "ابو ظبي", "المصفح"),
                                        ("0567778899", "شركة تجريبية", "الشارقة", "مدينة الشارقة")):
            client_id = self._new_id()
            self.add_client(client_id, phone, name=name,
                            client_number=self._client_number(client_id),
                            custom={"test": "N + F", "coordinates_text": "25.2,55.3"},
                            address={"city": city, "state": area, "address1": "شارع ١", "address2": "فيلا ٢"})

    # ---------- the three functions client.py picks between ----------

    def __call__(self, method, path, params=None, body=None):
        with self._lock:
            if self.fail_once and path.startswith(self.fail_once):
                self.fail_once = None
                self.failed.append((method, path, params, body))
                self.save()
                raise DaftraError("HTTP 500: simulated failure")
            self.calls.append((method, path, params, body))
            for pattern, handler in self.routes():
                match = re.fullmatch(pattern, f"{method} {path}")
                if match:
                    answer = handler(*match.groups(), params=params or {}, body=body)
                    self.save()
                    return answer
            self.save()
            raise self._no_route(method, path)

    def _no_route(self, method, path):
        """A call the fake does not know. A local portal must say so where the manager can read
        it; a test must fail outright instead of carrying on against a half-answered account."""
        if self.store:
            return DaftraError(f"دفترة التجريبية لا تعرف هذا النداء: {method} {path}")
        return AssertionError(f"FakeDaftra has no route for {method} {path}")

    def upload_file(self, content, filename, content_type, entity="invoice", field="invoices.documents"):
        """Keeps the file and gives it an id, as the account's file store does."""
        with self._lock:
            file_id = self._new_id()
            self.uploads.append({"id": file_id, "filename": filename, "content_type": content_type,
                                 "size": len(content), "entity": entity, "field": field})
            self.save()
        return file_id

    def invoice_pdf(self, invoice_id, pdf_url):
        """The invoice as a PDF. A test wants only that it is one; a local portal wants to open it."""
        if not self.draws_pdfs:
            return b"%PDF-1.4 fake invoice"
        return self._draw_pdf(invoice_id)

    def _draw_pdf(self, invoice_id) -> bytes:
        invoice = self.invoices.get(int(invoice_id)) or {}
        rows = "".join(
            f"<tr><td>{item.get('item') or ''}</td><td>{item.get('quantity')}</td>"
            f"<td>{item.get('unit_price')}</td></tr>"
            for item in invoice.get("items") or []
        )
        html = f"""<!doctype html><html dir="rtl"><head><meta charset="utf-8"><style>
          body {{ font-family: sans-serif; padding: 24px; }}
          .stamp {{ color: #b00; border: 2px solid #b00; padding: 6px 12px; display: inline-block; }}
          table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
          td, th {{ border: 1px solid #999; padding: 6px; text-align: right; }}
        </style></head><body>
          <p class="stamp">فاتورة تجريبية — لم تُنشأ في دفترة</p>
          <h2>فاتورة {invoice.get('no') or invoice_id}</h2>
          <p>التاريخ: {invoice.get('date') or ''}</p>
          <p>الإجمالي: {invoice.get('summary_total') or ''}</p>
          <table><tr><th>البند</th><th>الكمية</th><th>السعر</th></tr>{rows}</table>
        </body></html>"""
        from weasyprint import HTML
        return HTML(string=html).write_pdf()

    # ---------- the routes ----------

    def routes(self):
        return [
            (r"GET /api2/staff\.json", lambda **kw: self._page([{"Staff": s} for s in self.staff])),
            (r"GET /api2/products\.json", lambda **kw: self._page([{"Product": p} for p in self.products])),
            (r"GET /api2/treasuries\.json", lambda **kw: self._page([{"Treasury": t} for t in self.treasuries])),
            (r"GET /v2/api/entity/order_source/list/1", lambda **kw: {"data": self.order_sources}),
            (r"POST /v2/api/entity/order_source", self.create_order_source),
            (r"GET /v2/api/entity/order_source/(\d+)/1", self.get_order_source),
            (r"PUT /v2/api/entity/order_source/(\d+)", self.update_order_source),
            (r"GET /v2/api/entity/client_category/list/1", self.list_client_categories),
            (r"GET /api2/clients\.json", self.search_clients),
            (r"POST /api2/clients\.json", self.create_client),
            (r"GET /api2/clients/(\d+)\.json", self.get_client),
            (r"PUT /api2/clients/(\d+)\.json", self.update_client),
            (r"GET /api2/estimates\.json", self.list_estimates),
            (r"POST /api2/estimates\.json", self.create_estimate),
            (r"GET /api2/estimates/(\d+)\.json", self.get_estimate),
            (r"GET /api2/invoices\.json", self.list_invoices),
            (r"POST /api2/invoices\.json", self.create_invoice),
            (r"GET /api2/invoices/(\d+)\.json", self.get_invoice),
            (r"POST /api2/invoices/assign_work_order/(\d+)\.json", self.assign_work_order),
            (r"POST /api2/invoice_payments\.json", self.create_payment),
            (r"GET /api2/invoice_payments/(\d+)\.json", self.get_payment),
            (r"GET /api2/work_orders\.json", self.list_work_orders),
            (r"POST /api2/work_orders\.json", self.create_work_order),
            (r"GET /api2/work_orders/(\d+)\.json", self.get_work_order),
            (r"PUT /api2/work_orders/(\d+)\.json", self.update_work_order),
            (r"GET /v2/api/entity/work_order/(\d+)/3", self.read_work_order_v2),
            (r"GET /v2/api/entity/client/(\d+)/3", self.read_client_v2),
            (r"POST /v2/api/entity/invoice_document", self.attach_document),
        ]

    @staticmethod
    def _page(rows):
        return {"pagination": {"page_count": 1}, "data": rows}

    def list_client_categories(self, params, body):
        return {"data": self.categories, "last_page": 1}

    def create_order_source(self, params, body):
        source_id = max(s["id"] for s in self.order_sources) + 1
        self.order_sources.append({**body, "id": source_id})
        return {"message": "تم إضافة مصادر الطلب بنجاح", "id": source_id}

    def get_order_source(self, source_id, params, body):
        return next(s for s in self.order_sources if s["id"] == int(source_id))

    def update_order_source(self, source_id, params, body):
        # As Daftra does: without the id in the body, the "edit" adds a copy
        if "id" not in body:
            return self.create_order_source(params, body)
        source = self.get_order_source(source_id, params, None)
        source.update({key: value for key, value in body.items() if key != "id"})
        return {"message": "تم تحديث مصادر الطلب بنجاح", "id": source["id"]}

    # ---------- clients ----------

    def search_clients(self, params, body):
        words = str(params.get("keywords") or "")
        if not words:
            # Daftra's own search compares whole words, so a listing with no keywords gives all
            return {"data": [{"Client": c} for c in self.clients.values()]}
        # .get: a client created through the API holds only the fields the portal sent, and the
        # portal sends no phone2 (Daftra's own answer always carries every field, empty or not)
        rows = [c for c in self.clients.values()
                if words in (c.get("phone1") or "", c.get("phone2") or "", c.get("business_name") or "")]
        return {"data": [{"Client": c} for c in rows]}

    def create_client(self, params, body):
        client_id = self._new_id()
        # Every field a client is read back with, so what the portal left out answers as empty
        # rather than missing, as Daftra's own answer does
        fields = {"business_name": "", "phone1": "", "phone2": "", **body["Client"]}
        self.clients[client_id] = {**fields, "id": str(client_id),
                                   "client_number": self._client_number(client_id),
                                   "custom": body.get("le_custom_data_client")}
        return {"id": client_id}

    def get_client(self, client_id, params, body):
        client = self.clients.get(int(client_id))
        if client is None:
            raise NotFound("HTTP 404: no client")
        return {"data": {"Client": client}}

    def read_client_v2(self, client_id, params, body):
        """The read API v2, the only one that gives back a client's custom fields."""
        client = self.clients.get(int(client_id))
        if client is None:
            raise NotFound("HTTP 404: no client")
        return {**client, "client_custom_data": client.get("custom")}

    def update_client(self, client_id, params, body):
        client = self.clients[int(client_id)]
        custom = body.get("le_custom_data_client") or client.get("custom")
        # The account demands these on every save; empty means refused, as Daftra does
        if not (custom or {}).get("test") or not (custom or {}).get("coordinates_text"):
            raise DaftraError('HTTP 400: Bad Request — {"اسم الجهاز": ["هذا الحقل مطلوب ولا يمكن ان يكون فارغ"], '
                              '"Coordinates": ["هذا الحقل مطلوب ولا يمكن ان يكون فارغ"]}')
        fields = dict(body["Client"])
        # Daftra builds the name out of the name fields of the body it is given: a save that leaves
        # business_name out comes back with the empty first and last name joined by a space, which
        # is how client 4053 lost its name on 22 Oct 2026
        if "business_name" not in fields:
            fields["business_name"] = f"{fields.get('first_name', '')} {fields.get('last_name', '')}"
        client.update(fields)
        if body.get("le_custom_data_client"):
            client["custom"] = body["le_custom_data_client"]
        return {"result": "successful"}

    # ---------- invoices ----------

    def _invoice_out(self, invoice):
        total = float(invoice["summary_total"])
        paid = invoice["initial_paid"] + sum(p["amount"] for p in invoice["payments"])
        client = self.clients.get(int(invoice["client_id"]), {})
        return {**{k: v for k, v in invoice.items() if k not in ("payments", "documents", "initial_paid")},
                "summary_unpaid": str(round(total - paid, 2)),
                "invoice_pdf_url": f"https://fake.daftra.test/invoices/view/{invoice['id']}.pdf?hash=x",
                "Client": {"client_number": client.get("client_number", "")},
                "InvoicePayment": [{"id": str(p["id"]), "notes": p["notes"]} for p in invoice["payments"]],
                "InvoiceDocument": [{"id": str(i + 1), "invoice_id": invoice["id"], "document_id": str(d)}
                                    for i, d in enumerate(invoice["documents"])]}

    def list_invoices(self, params, body):
        rows = [i for i in self.invoices.values() if str(i["client_id"]) == str(params.get("client_id"))]
        return {"data": [{"Invoice": self._invoice_out(i)} for i in rows]}

    def create_invoice(self, params, body):
        invoice_id = self._new_id()
        fields, items = body["Invoice"], body["InvoiceItem"]
        total = sum(item["unit_price"] * item["quantity"] for item in items) + fields.get("adjustment_value", 0)
        self.invoices[invoice_id] = {**fields, "id": str(invoice_id), "no": f"0{invoice_id}", "draft": "0",
                                     "summary_total": str(round(total, 2)), "items": items, "payments": [],
                                     "created": datetime.now(UAE).strftime("%Y-%m-%d %H:%M:%S"),
                                     "documents": [], "initial_paid": 0.0}
        return {"id": invoice_id}

    def get_invoice(self, invoice_id, params, body):
        invoice = self.invoices.get(int(invoice_id))
        if invoice is None:
            raise NotFound("HTTP 404: no invoice")
        return {"data": {"Invoice": self._invoice_out(invoice)}}

    # ---------- estimates (عروض الأسعار) ----------

    def list_estimates(self, params, body):
        rows = [e for e in self.estimates.values() if str(e["client_id"]) == str(params.get("client_id"))]
        return {"data": [{"Estimate": self._invoice_out(e)} for e in rows]}

    def create_estimate(self, params, body):
        """POST /api2/estimates.json, whose body is an invoice's: {"Invoice": …, "InvoiceItem": […]}."""
        estimate_id = self._new_id()
        fields, items = body["Invoice"], body["InvoiceItem"]
        total = sum(item["unit_price"] * item["quantity"] for item in items) + fields.get("adjustment_value", 0)
        self.estimates[estimate_id] = {**fields, "id": str(estimate_id), "no": f"E{estimate_id}", "type": "3",
                                       "draft": "0", "summary_total": str(round(total, 2)), "items": items,
                                       "payments": [], "documents": [], "initial_paid": 0.0,
                                       "created": datetime.now(UAE).strftime("%Y-%m-%d %H:%M:%S")}
        return {"id": estimate_id}

    def get_estimate(self, estimate_id, params, body):
        estimate = self.estimates.get(int(estimate_id))
        if estimate is None:
            raise NotFound("HTTP 404: no estimate")
        return {"data": {"Estimate": self._invoice_out(estimate)}}

    def attach_document(self, params, body):
        self.invoices[int(body["invoice_id"])]["documents"].append(body["document_id"])
        return {"message": "added", "id": len(self.uploads)}

    def assign_work_order(self, invoice_id, params, body):
        self.invoices[int(invoice_id)]["work_order_id"] = str(body["Invoice"]["work_order_id"])
        return {"result": "successful"}

    # ---------- payments ----------

    def create_payment(self, params, body):
        payment_id = self._new_id()
        fields = body["InvoicePayment"]
        payment = {**fields, "id": payment_id, "code": f"R{payment_id}"}
        self.payments[payment_id] = payment
        self.invoices[int(fields["invoice_id"])]["payments"].append(payment)
        return {"id": payment_id}

    def get_payment(self, payment_id, params, body):
        return {"data": {"InvoicePayment": self.payments[int(payment_id)]}}

    # ---------- work orders ----------

    def list_work_orders(self, params, body):
        rows = [w for w in self.work_orders.values() if str(w["client_id"]) == str(params.get("client_id"))]
        return {"data": [{"WorkOrder": w} for w in rows]}

    def create_work_order(self, params, body):
        work_order_id = self._new_id()
        self.work_orders[work_order_id] = {**body["WorkOrder"], "id": str(work_order_id),
                                           "number": f"00100{work_order_id}", "custom": {}}
        return {"id": work_order_id}

    def get_work_order(self, work_order_id, params, body):
        return {"data": {"WorkOrder": self.work_orders[int(work_order_id)]}}

    def update_work_order(self, work_order_id, params, body):
        self.work_orders[int(work_order_id)]["custom"] = dict(body.get("CustomModel") or {})
        return {}

    def read_work_order_v2(self, work_order_id, params, body):
        return {"custom_data": self.work_orders[int(work_order_id)]["custom"]}

    # ---------- helpers for assertions ----------

    def posted(self, path):
        return [body for method, called, _, body in self.calls if method == "POST" and called == path]


# ---------- the account this process uses ----------

_account: FakeDaftra | None = None
_account_lock = threading.Lock()


def account() -> FakeDaftra:
    """The local portal's fake account, kept in the uploads folder so a restart and the
    commands see the same one."""
    global _account
    with _account_lock:
        if _account is None:
            from ...core.config import UPLOAD_DIR
            _account = FakeDaftra(store=UPLOAD_DIR / "fake_daftra.json", first_id=FIRST_LOCAL_ID,
                                  numbered_clients=True, draws_pdfs=True)
        return _account


def use(replacement: FakeDaftra | None):
    """Puts an account in place of the one this process would make itself — a test's own."""
    global _account
    with _account_lock:
        _account = replacement


def call(method: str, path: str, params: dict | None = None, body: dict | list | None = None) -> dict:
    return account()(method, path, params, body)


def upload_file(content: bytes, filename: str, content_type: str,
                entity: str = "invoice", field: str = "invoices.documents") -> int:
    return account().upload_file(content, filename, content_type, entity, field)


def invoice_pdf(invoice_id: int, pdf_url: str) -> bytes:
    return account().invoice_pdf(invoice_id, pdf_url)
