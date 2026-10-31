"""One function per call the portal makes to Daftra, named after what it does there.

Everything above this file asks for a thing («the active treasuries», «this client's category»)
and never writes a Daftra path. The verbs at the top are how those calls are made; `client.py`
carries them out.
"""

import json
import re
import urllib.error
from concurrent.futures import ThreadPoolExecutor

from ...core.config import settings
from ...core.text import fold_arabic, squash
from . import cache, client
from .errors import DaftraError

# A product's `type` in Daftra: 1 is a product with stock, 2 a service
PRODUCT_SERVICE = 2
# What an assignment (item_staff) is of. Daftra keeps every kind of them in one list.
WORK_ORDER_ITEM = 8


# ---------- The verbs ----------


def get(resource: str, params: dict | None = None) -> dict:
    return client.call("GET", f"/api2/{resource}", params)


def create(resource: str, body: dict, params: dict | None = None) -> int:
    """Adds a record, e.g. create("invoices.json", {"Invoice": ...}), and returns its new id."""
    result = client.call("POST", f"/api2/{resource}", params, body)
    if not result.get("id"):
        raise DaftraError(f"Daftra did not return an id: {json.dumps(result, ensure_ascii=False)[:300]}")
    return int(result["id"])


def post(resource: str, body: dict) -> dict:
    """An action that is not "add a record", e.g. linking a work order to an invoice."""
    return client.call("POST", f"/api2/{resource}", None, body)


def update(resource: str, body: dict):
    """Changes a record, e.g. update("clients/12.json", {"Client": {...}}); Daftra changes only the fields sent."""
    client.call("PUT", f"/api2/{resource}", None, body)


def update_unconfirmed(resource: str, body: dict):
    """Like update(), for an edit Daftra saves but then answers with a redirect to an HTML error
    page (a work order's CustomModel does this). Only a real refusal is raised; the caller must read
    the record back to know whether it saved."""
    try:
        client.call("PUT", f"/api2/{resource}", None, body)
    except DaftraError as error:
        cause = error.__cause__
        redirected = isinstance(cause, urllib.error.HTTPError) and 300 <= cause.code < 400
        if not (redirected or isinstance(cause, ValueError)):
            raise


def read_v2(entity: str, record_id: int) -> dict:
    """One record from the read API v2, with its related data (e.g. a work order's custom_data)."""
    return client.call("GET", f"/v2/api/entity/{entity}/{record_id}/3")


def attach_invoice_document(invoice_id: int, file_id: int):
    """Shows an uploaded file on the invoice in Daftra, as one of its attachments.

    document_id, not file_id: Daftra accepts file_id and then stores 0. Sending it with the
    invoice's own edit instead does nothing — api2 answers "successful" and saves none of it,
    while still replacing every invoice field left out — so it goes through API v2's entity.
    """
    client.call("POST", "/v2/api/entity/invoice_document", None, {"invoice_id": invoice_id, "document_id": file_id})


def work_order_staff(work_order_id: int) -> list[int]:
    """Who a work order is assigned to (معلومات الموظفين المعينين). The work order's own
    assigned_users stays empty; these are only in the entity they are kept in."""
    body = client.call("GET", "/v2/api/entity/item_staff/list/1",
                       {"filter[item_id]": work_order_id, "filter[item_type]": WORK_ORDER_ITEM, "limit": 100})
    return [int(row["staff_id"]) for row in body.get("data", [])]


def assign_work_order(work_order_id: int, staff_id: int, assigned_by: int):
    """Adds someone to those who hold a work order. Not in Daftra's docs: a POST to the v2 entity
    path, proven on our account (daftra-api.md 3a). The API cannot take an assignment off again."""
    client.call("POST", "/v2/api/entity/item_staff", None,
                {"item_id": work_order_id, "item_type": WORK_ORDER_ITEM, "staff_id": staff_id,
                 "assigned_by": assigned_by})


def all_records(resource: str, model: str, workers: int = 4) -> list[dict]:
    """Every page of a list, e.g. all_records("clients", "Client")."""
    first = get(f"{resource}.json", {"limit": 100, "page": 1})
    page_count = first.get("pagination", {}).get("page_count", 1)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rest = list(pool.map(lambda page: get(f"{resource}.json", {"limit": 100, "page": page}),
                             range(2, page_count + 1)))
    return [row[model] for page in (first, *rest) for row in page.get("data", [])]


# ---------- Lists used as drop-downs (cached, they change rarely) ----------


def list_staff_members() -> list[dict]:
    """Active Daftra staff with their ids, for linking a portal user to one."""
    def load():
        members = [
            {"id": int(member["id"]),
             "name": squash(member.get("full_name") or f"{member.get('name') or ''} {member.get('last_name') or ''}")}
            for member in all_records("staff", "Staff")
            if member.get("active") == "1"
        ]
        return sorted((m for m in members if m["name"]), key=lambda m: m["name"])

    return cache.cached("staff_members", load)


def list_staff() -> list[str]:
    """Names of active Daftra staff, each once, for the forms' staff fields (e.g. «اسم المحصل»).
    Read from the same cached list as list_staff_members, so Daftra is asked once for both."""
    return sorted({member["name"] for member in list_staff_members()})


def list_clients() -> list[dict]:
    """Every Daftra client, raw, for the job that keeps our local copy in step."""
    return all_records("clients", "Client")


def list_products() -> list[dict]:
    """Every Daftra product, raw and including deactivated ones, for refreshing the catalog's
    linked products."""
    return all_records("products", "Product")


def products_named(name: str) -> list[dict]:
    """Daftra's active services of this name, raw. Its search also finds parts of a name, codes and
    tags, so the names are compared here; a stock-tracked product of the same name does not count."""
    wanted = same_name(name)
    rows = (row["Product"] for row in get("products.json", {"keywords": name, "limit": 100}).get("data", []))
    return [row for row in rows if same_name(row.get("name") or "") == wanted
            and str(row.get("type")) == str(PRODUCT_SERVICE) and str(row.get("status") or "0") == "0"]


def list_treasuries() -> list[dict]:
    """Active treasuries and bank accounts a payment can be received into."""
    def load():
        rows = all_records("treasuries", "Treasury")
        return sorted(
            ({"id": int(row["id"]), "name": squash(row.get("name"))} for row in rows if row.get("active") == "1"),
            key=lambda row: row["name"],
        )

    return cache.cached("treasuries", load)


def list_client_categories() -> list[dict]:
    """Daftra's client categories (a client's التصنيف, e.g. «العين العامره»). Only the read API v2 lists them."""
    def load():
        rows, page = [], 1
        while True:
            body = client.call("GET", "/v2/api/entity/client_category/list/1", {"limit": 100, "page": page})
            rows += body.get("data", [])
            if page >= (body.get("last_page") or 1):
                break
            page += 1
        named = ({"id": int(row["id"]), "name": squash(row.get("name"))} for row in rows)
        return sorted((row for row in named if row["name"]), key=lambda row: row["name"])

    return cache.cached("client_categories", load)


def client_category(client_id: int) -> dict | None:
    """The client's current category as {"id", "name"}, or None if it has none."""
    row = get(f"clients/{client_id}.json").get("data", {}).get("Client", {})
    if not row.get("category_id"):
        return None
    return {"id": int(row["category_id"]), "name": squash(row.get("category"))}


def client_invoices(client_id: int) -> list[dict]:
    """The client's invoices as Daftra holds them, raw rows in Daftra's own order."""
    return get("invoices.json", {"client_id": client_id, "limit": 100}).get("data", [])


# ---------- Order sources (an invoice's مصدر الطلب) ----------

ORDER_SOURCES = "order_sources"


def all_order_sources() -> list[dict]:
    """Every order source, active or not, in Daftra's display order.
    Not cached: the admin page shows them as they are now. Only the read API v2 lists them."""
    body = client.call("GET", "/v2/api/entity/order_source/list/1", {"limit": 100})
    rows = sorted(body.get("data", []), key=lambda row: (row.get("display_order") or 0, int(row["id"])))
    return [{"id": int(row["id"]), "name": squash(row.get("name")), "active": row.get("status") == 1,
             "display_order": row.get("display_order") or 0} for row in rows]


def list_order_sources() -> list[dict]:
    """Active order sources, the ones the forms offer."""
    def load():
        return [{"id": row["id"], "name": row["name"]} for row in all_order_sources() if row["active"]]

    return cache.cached(ORDER_SOURCES, load)


def create_order_source(name: str) -> int:
    """Adds an active order source after the others, and returns its id. Not in Daftra's docs: a
    POST to the v2 entity path, proven on our account (daftra-api.md 4b)."""
    last = max((row["display_order"] for row in all_order_sources()), default=0)
    result = client.call("POST", "/v2/api/entity/order_source",
                         body={"name": name, "status": 1, "display_order": last + 1,
                               "branch_id": settings.daftra_branch_id})
    if not result.get("id"):
        raise DaftraError(f"Daftra did not return an id: {json.dumps(result, ensure_ascii=False)[:300]}")
    # The forms offer it from now on, not after the cached list runs out
    cache.forget(ORDER_SOURCES)
    return int(result["id"])


def set_order_source_active(source_id: int, active: bool) -> dict:
    """Turns an order source on or off and returns it as Daftra then holds it.

    The edit must carry the id in its body as well as its path: without it Daftra answers
    "updated" but adds a copy instead (daftra-api.md 4b). Every field is sent, as read just before.
    """
    row = client.call("GET", f"/v2/api/entity/order_source/{source_id}/1")
    body = {"id": source_id, "name": row.get("name") or "", "status": 1 if active else 0,
            "display_order": row.get("display_order") or 0,
            "branch_id": row.get("branch_id") or settings.daftra_branch_id}
    result = client.call("PUT", f"/v2/api/entity/order_source/{source_id}", body=body)
    if str(result.get("id")) != str(source_id):
        raise DaftraError(f"Daftra saved the change as another order source (id {result.get('id')}), not {source_id}")
    saved = client.call("GET", f"/v2/api/entity/order_source/{source_id}/1")
    if (saved.get("status") == 1) != active:
        raise DaftraError("Daftra answered that it saved the change, but the order source did not change")
    cache.forget(ORDER_SOURCES)
    return {"id": source_id, "name": squash(saved.get("name")), "active": active,
            "display_order": saved.get("display_order") or 0}


def same_name(name: str) -> str:
    """Two names that differ only in spacing, punctuation, letter case or Arabic spelling are one
    («Website - جديد» and «website-جديد»)."""
    return re.sub(r"[\W_]+", "", fold_arabic(name).lower())
