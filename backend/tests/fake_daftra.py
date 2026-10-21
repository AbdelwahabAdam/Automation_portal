"""An in-memory stand-in for our Daftra account, answering the calls app.daftra makes.

Every call is recorded in `calls` as (method, path, params, body), so a test can check exactly
what the portal would have sent. Nothing here ever reaches the network.
"""

import re

from app.daftra import DaftraError, NotFound


class FakeDaftra:
    def __init__(self):
        # Calls that were answered, and those refused by fail_once
        self.calls = []
        self.failed = []
        self.clients = {}
        self.invoices = {}
        self.payments = {}
        self.work_orders = {}
        self.staff = [{"id": "71", "full_name": "Sales One", "active": "1"},
                      {"id": "40", "full_name": "Manager One", "active": "1"},
                      {"id": "9", "full_name": "Old Staff", "active": "0"}]
        self.treasuries = [{"id": "13", "name": "ADIB NEW CURRENT", "active": "1"},
                           {"id": "9", "name": "خزينه المكتب", "active": "1"},
                           {"id": "99", "name": "Closed", "active": "0"}]
        self.order_sources = [{"id": 16, "name": "Sales-جديد", "status": 1, "display_order": 2},
                              {"id": 12, "name": "water", "status": 1, "display_order": 1},
                              {"id": 3, "name": "old", "status": 0, "display_order": 0}]
        self.next_id = 7000
        # Set to a path prefix (e.g. "/api2/invoice_payments.json") to make that call fail once
        self.fail_once = None

    def _new_id(self):
        self.next_id += 1
        return self.next_id

    def add_client(self, client_id, phone, name="Existing", category_id=None, client_number=None):
        self.clients[client_id] = {"id": str(client_id), "business_name": name, "phone1": phone, "phone2": "",
                                   "client_number": client_number or f"{client_id:06d}",
                                   "category_id": str(category_id) if category_id else "", "category": ""}

    def add_invoice(self, client_id, total, paid=0.0, no=None, draft="0"):
        invoice_id = self._new_id()
        self.invoices[invoice_id] = {
            "id": str(invoice_id), "client_id": str(client_id), "no": no or f"0{invoice_id}", "draft": draft,
            "date": "2026-10-18", "po_number": "", "summary_total": str(total), "items": [], "payments": [],
            "initial_paid": paid,
        }
        return invoice_id

    # ---------- what app.daftra._call is replaced with ----------

    def __call__(self, method, path, params=None, body=None):
        if self.fail_once and path.startswith(self.fail_once):
            self.fail_once = None
            self.failed.append((method, path, params, body))
            raise DaftraError("HTTP 500: simulated failure")
        self.calls.append((method, path, params, body))
        for pattern, handler in self.routes():
            match = re.fullmatch(pattern, f"{method} {path}")
            if match:
                return handler(*match.groups(), params=params or {}, body=body)
        raise AssertionError(f"FakeDaftra has no route for {method} {path}")

    def routes(self):
        return [
            (r"GET /api2/staff\.json", lambda **kw: self._page([{"Staff": s} for s in self.staff])),
            (r"GET /api2/treasuries\.json", lambda **kw: self._page([{"Treasury": t} for t in self.treasuries])),
            (r"GET /v2/api/entity/order_source/list/1", lambda **kw: {"data": self.order_sources}),
            (r"GET /api2/clients\.json", self.search_clients),
            (r"POST /api2/clients\.json", self.create_client),
            (r"GET /api2/clients/(\d+)\.json", self.get_client),
            (r"PUT /api2/clients/(\d+)\.json", self.update_client),
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
        ]

    @staticmethod
    def _page(rows):
        return {"pagination": {"page_count": 1}, "data": rows}

    # ---------- clients ----------

    def search_clients(self, params, body):
        words = str(params.get("keywords") or "")
        rows = [c for c in self.clients.values() if words in (c["phone1"], c["phone2"], c["business_name"])]
        return {"data": [{"Client": c} for c in rows]}

    def create_client(self, params, body):
        client_id = self._new_id()
        fields = body["Client"]
        self.clients[client_id] = {**fields, "id": str(client_id), "client_number": f"{client_id:06d}",
                                   "custom": body.get("le_custom_data_client")}
        return {"id": client_id}

    def get_client(self, client_id, params, body):
        client = self.clients.get(int(client_id))
        if client is None:
            raise NotFound("HTTP 404: no client")
        return {"data": {"Client": client}}

    def update_client(self, client_id, params, body):
        self.clients[int(client_id)].update(body["Client"])
        return {"result": "successful"}

    # ---------- invoices ----------

    def _invoice_out(self, invoice):
        total = float(invoice["summary_total"])
        paid = invoice["initial_paid"] + sum(p["amount"] for p in invoice["payments"])
        client = self.clients.get(int(invoice["client_id"]), {})
        return {**{k: v for k, v in invoice.items() if k not in ("payments", "initial_paid")},
                "summary_unpaid": str(round(total - paid, 2)),
                "invoice_pdf_url": f"https://fake.daftra.test/invoices/view/{invoice['id']}.pdf?hash=x",
                "Client": {"client_number": client.get("client_number", "")},
                "InvoicePayment": [{"id": str(p["id"]), "notes": p["notes"]} for p in invoice["payments"]]}

    def list_invoices(self, params, body):
        rows = [i for i in self.invoices.values() if str(i["client_id"]) == str(params.get("client_id"))]
        return {"data": [{"Invoice": self._invoice_out(i)} for i in rows]}

    def create_invoice(self, params, body):
        invoice_id = self._new_id()
        fields, items = body["Invoice"], body["InvoiceItem"]
        total = sum(item["unit_price"] * item["quantity"] for item in items) + fields.get("adjustment_value", 0)
        self.invoices[invoice_id] = {**fields, "id": str(invoice_id), "no": f"0{invoice_id}", "draft": "0",
                                     "summary_total": str(round(total, 2)), "items": items, "payments": [],
                                     "initial_paid": 0.0}
        return {"id": invoice_id}

    def get_invoice(self, invoice_id, params, body):
        invoice = self.invoices.get(int(invoice_id))
        if invoice is None:
            raise NotFound("HTTP 404: no invoice")
        return {"data": {"Invoice": self._invoice_out(invoice)}}

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
