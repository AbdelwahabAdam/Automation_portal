# The portal's architecture

How the code is arranged, why, and what to do when you add something. The README covers running
the portal and what it does for its users; this covers how it is built.

1. [The pattern in one page](#the-pattern-in-one-page)
2. [The layers, and the one rule](#the-layers-and-the-one-rule)
3. [Inside a module](#inside-a-module)
4. [The file structure](#the-file-structure)
5. [One click through every layer](#one-click-through-every-layer)
6. [Adding a form](#adding-a-form)
7. [A form's fields](#a-forms-fields)
8. [What approving a form creates in Daftra](#what-approving-a-form-creates-in-daftra)
9. [Adding other things](#adding-other-things)
10. [What the tests enforce](#what-the-tests-enforce)

---

## The pattern in one page

The portal is a **modular monolith**: one app, one database, one deploy, with the code divided by
business area rather than by technical kind. There is no service mesh, no queue and no Redis — on
an 8 GB server, that would be cost without benefit.

Three ideas carry most of the weight:

**Modules by business area.** `identity`, `requests`, `clients`, `catalog`, `invoicing`, `audit`,
`notifications`, `lookups`, `form_engine`, `system`. Each owns its tables and is reached only
through its `__init__.py`. Not one module per form: all forms share one table, one lifecycle, one
validator and one review queue.

**Forms are plugins.** Each of the 19 forms is a folder under `app/forms/<key>/` holding its
fields, and hooks only where it differs from every other form. Nothing outside that folder names
a form — a search for a form key elsewhere in `app/` finds nothing. Adding a form is a folder and
one line; it needs no router, no table, no migration and no frontend change.

**Layers that only point downwards.** A file imports from its own layer or a lower one, never a
higher one. `tests/test_architecture.py` reads every import and fails otherwise, so the shape
cannot quietly rot.

---

## The layers, and the one rule

```
main.py · jobs/            entry points: may import anything
      ↓
forms/<key>/               the forms
      ↓
modules/<module>/          business areas: each other only through __init__.py, never in a circle
      ↓
integrations/daftra/       knows nothing about modules or forms
      ↓
core/                      knows nothing above it
```

The rule has three parts, and each is a test:

1. **Never upwards.** `core` cannot import `modules`; `integrations` cannot import `forms`.
2. **Through the front door.** A module reaches another only through its `__init__.py`:
   `from ..catalog import Product`, never `from ..catalog.repo import products_by_name`.
3. **No circles.** Not directly, and not round a longer loop.

Two exemptions: `modules/models.py` may import every module's models (that is its whole job), and
`main.py` and `jobs/` may import anything (they are the entry points).

### When two modules seem to need each other

They don't, and the fix is always one of three moves. Each is in the code already:

| Situation | What we did |
|---|---|
| `identity` writes to the activity log, and the log's page needs the list of users | `audit` sits **below** everything that logs. `identity` hands it the user list at import: `audit.set_user_lister(repo.listed_users)`. Same for `notifications.add_value_labels`. |
| `clients` and `invoicing` both raise "the Daftra documents could not be created" | `SyncError` lives in `core/errors.py`, below both. |
| `clients` needed a whole `Request` to update a customer | Narrow the signature: `update_client(daftra_client_id, data)`. It now needs to know nothing about requests. |

And the one that matters most: **`requests` does not import `invoicing`.** Approving a request
asks the *form* what to create, through the registry. `invoicing` imports `requests` (to save a
PDF on it), one direction only.

### Errors

A service never raises `HTTPException` and never knows it is behind HTTP — that is what lets a
cron job call the same function a page does. It raises from `core/errors.py`, and one handler in
`main.py` turns each into the status the route always answered:

| Error | Status | |
|---|---|---|
| `BadRequest` | 400 | what was sent cannot be used at all |
| `Unauthorized` | 401 | not signed in, or wrong credentials |
| `Forbidden` | 403 | signed in, but may not do this |
| `NotFound` | 404 | |
| `Conflict` | 409 | refused because of the state of things |
| `TooManyRequests` | 429 | |
| `Invalid` | 422 | failed the rules; `fields={...}` becomes `{"detail": {"errors": {...}}}` |
| `ExternalFailure` | 502 | Daftra or the mail server failed us |
| `Unavailable` | 503 | try again shortly |
| `SyncError` | 502 or 409 | the Daftra documents could not be created; 502 when Daftra itself refused |

### Who is acting

Routers pass an **`Actor`** (`core/context.py`) into services instead of FastAPI's request: the
user, their IP and their browser. A job passes `Actor.system()`, which the activity log records as
«المزامنة الليلية». In a router you get one with `Depends(acting(<the dependency that finds the user>))`.

---

## Inside a module

Each module has the files it needs and no more.

| File | Holds | Never |
|---|---|---|
| `__init__.py` | what other modules may use: re-exported functions, classes, errors | logic of its own |
| `router.py` | the HTTP routes: read the input, call the service, return the answer | query the database, decide business rules, commit |
| `schemas.py` | the Pydantic shapes of what comes in and goes out | touch the database |
| `service.py` | the business rules, one function per thing a user or job does; **commits** | raise `HTTPException` |
| `repo.py` | the SQLAlchemy queries on this module's own tables | commit, call other modules, decide anything |
| `models.py` | this module's tables | `relationship()` to another module's model, except `User` |

A layer that outgrows one file splits **by topic** into a folder of the same name —
`identity/service/auth.py`, `identity/router/users.py`, `requests/service/review.py`. What it
splits into is still that layer and follows that layer's rules.

There is no `BaseRepository`. SQLAlchemy's session already is one; a repo function exists because
a query has a name worth giving it.

A module owns its tables: only its own code writes them, and everyone else goes through its
`__init__`. Foreign keys across modules are fine; `relationship()` names the class as a string
(`relationship("User", ...)`) so no module imports another's models.

---

## The file structure

### Backend

```
backend/app/
├── main.py                      builds the app: mounts the routers, maps errors, starts the warm-up
├── core/                        shared by everything; no business rules
│   ├── config.py                settings (one Settings object, read from .env)
│   ├── database.py              engine, Session, Base, get_db, run_migrations
│   ├── security.py              the token, hashing, current_user, require(), acting()
│   ├── permissions.py           every permission, and the menu built from them
│   ├── errors.py                what a service raises, and the status each becomes
│   ├── context.py               Actor: who is acting and from where
│   └── text.py                  Arabic digits, UAE time, phone numbers, Arabic folding
├── integrations/
│   └── daftra/                  the Daftra client — the only code that talks to Daftra
│       ├── client.py            the one switch: hands every call to live or fake (DAFTRA_FAKE)
│       ├── live.py              HTTP: calls, retries, Daftra's errors, file upload, invoice PDF
│       ├── fake.py              the stand-in: the same three calls, no network
│       ├── resources.py         one function per call the portal makes
│       ├── cache.py             the lists kept for a while (staff, treasuries, order sources)
│       └── errors.py            DaftraError, NotFound
├── modules/
│   ├── identity/                login, two-step codes, password links, account, users, roles
│   ├── requests/                drafts, submitting, attachments, history, review, the documents
│   ├── form_engine/             FormSpec, the registry, the field builders, shared choices, validation
│   ├── clients/                 the customers: our copy of Daftra's, addresses, categories, map links
│   ├── catalog/                 products and packages
│   ├── invoicing/               what approving creates in Daftra, and the PDFs the portal draws
│   ├── lookups/                 Daftra's staff, treasuries and order sources (+ the order sources page)
│   ├── audit/                   the activity log and its page
│   ├── notifications/           email: sending, templates, the test page
│   ├── system/                  which version is running
│   └── models.py                imports every module's models, for SQLAlchemy and Alembic
├── forms/                       one folder per form — see "Adding a form"
└── jobs/                        python -m app.jobs <name>
```

Only `main.py`, `__init__.py`, those five folders and the old command aliases live at the root of
`app/`. The aliases (`import_clients.py`, …) are two-line shims kept until the server's cron has
been moved to `python -m app.jobs …`.

### Frontend

The frontend mirrors the backend.

```
frontend/src/
├── main.jsx
├── app/        App.jsx (shell and menus) · routes.jsx (a path per screen, and the redirects) · nav.js (icons)
├── api/        the frontend's client of the backend, one file per backend module
│               http.js (fetch, the token, ApiError) · identity.js · requests.js · review.js ·
│               clients.js · catalog.js · lookups.js · audit.js · notifications.js · jobs.js · system.js
├── modules/
│   ├── identity/        Login · SetPassword · Account · Users · Roles
│   ├── requests/        FormsCatalog · RequestForm · form/ · MyRequests · RequestList · RequestView ·
│   │                    Review · screens.jsx (the route-aware wrappers) · validation.js · useFormData.js
│   ├── catalog/ · lookups/ · audit/ · notifications/ · system/
├── ds/         the design system: components, tokens, styles, the search matcher
└── lib/        format.js (how dates and amounts are written) · hooks.js · brand.js
```

Two rules here:

- **Every API path lives in `src/api/` and nowhere else.** A screen calls
  `requests.updateRequest(id, body)`, never `api('/requests/…')`.
- **There is no folder per form.** The engine draws every form from its definition. If a future
  form needs a field the engine lacks, add a field *type* to the engine and every form can use it.

---

## One click through every layer

A manager clicks «اعتماد» on a balance payment:

```
Review.jsx → api/review.js                     frontend: decide(id, 'approve', { revision })
POST /api/review/requests/42/approve           HTTP
modules/requests/router/review.py              transport: reads the input, builds the Actor
modules/requests/service/review.py             locks the row, checks form.balance_payment.review,
                                               asks the form what to create
forms/balance_payment/hooks.py                 the form: what this one creates
modules/invoicing/invoice.py                   the steps: the payment, the receipt, the PDFs
                                               (estimate.py for the offer طلب عرض سعر makes)
integrations/daftra/resources.py → client.py   the Daftra client
  → live.py (the HTTP call) or fake.py         DAFTRA_FAKE decides
```

Read it the other way to see the rule: every arrow points downwards, and `requests` never names a
form or imports `invoicing`.

---

## Adding a form

Nineteen forms exist (6 visible, 13 hidden); a twentieth is a folder and one line. **No router, table, migration or
frontend change.**

### 1. The folder

```
app/forms/<key>/
├── __init__.py      the FormSpec — what the form is
├── definition.py    its sections and fields, and any choices only it offers
└── hooks.py         only if it differs: a check, or what approving it creates
```

The **key is stored on every request made with that form, so it may never be renamed.** Pick it
once, in `snake_case`.

### 2. The `FormSpec`

`app/forms/site_visit/__init__.py`:

```python
from ...modules.form_engine import FormSpec, register

from . import definition, hooks

register(FormSpec(
    key="site_visit",                # stored on every request: never rename
    label="طلب زيارة موقع",
    icon="map-pin",                  # any name from the design system's icon set
    description="تسجيل طلب زيارة موقع",
    sections=definition.SECTIONS,
    visible=True,                    # False: no new requests; old ones still open and reviewable
    daftra_note="ويُنشأ في دفترة ...",  # only if approving creates something there
    validate=hooks.validate,         # optional
    on_approve=hooks.on_approve,     # optional
))
```

A form with neither hook needs only `__init__.py` and `definition.py`, and its `__init__` imports
just `definition`.

| Field | |
|---|---|
| `visible` | `False` takes it out of النماذج without touching the requests already made with it. The 13 hidden forms are defined and closed. |
| `daftra_note` | Shown to the manager before approving, saying what will be created in Daftra. Set it exactly when `on_approve` is set — a test enforces that. |
| `invoiced` | **Derived**, not set: it is `on_approve is not None`. `RequestView.jsx` reads it. |

### 3. Register it

Add one line to `app/forms/__init__.py`, in the position you want it to appear in النماذج:

```python
from . import (
    new_sale,
    ...
    site_visit,
)
FORMS = (new_sale, ..., site_visit)
```

That import is what registers the form **and declares its three permissions**.

### 4. Access — it starts closed

Registering declares `form.site_visit.submit`, `form.site_visit.view` and
`form.site_visit.review`. Until an admin grants one, **only admins see the form.** Nothing else is
needed: the three keys appear by themselves in الإدارة ← الأدوار والصلاحيات, under both tabs.

| Permission | Lets the user |
|---|---|
| `form.<key>.submit` | see it in النماذج, fill it, save drafts, submit, correct their own returned requests |
| `form.<key>.view` | see everyone's requests of this form, with their files, without changing them |
| `form.<key>.review` | see them in المراجعة and approve or return them |

### 5. Pin it with a test

`tests/forms/test_form_registry.py` lists every form key, which are visible and which are
invoiced. Add yours to those lists — that list is what makes renaming a key a failing test rather
than a silent loss of every request made with it.

### 6. That's it

No migration (all forms share the `requests` table, whose `data` is JSONB). No frontend change
(the icon and description come with the form from `GET /api/form-types`). No route (the engine
serves every form from `/forms/<key>`).

---

## A form's fields

`definition.py` holds `SECTIONS`: a list of sections, each a list of fields. Everything comes from
`modules.form_engine` — **that `__init__` is the only way in**, never
`form_engine.fields` or `form_engine.options`.

```python
"""The fields of طلب زيارة موقع, as sections (form_engine has the building blocks)."""

from ...modules.form_engine import NOTES, attachments, f, files, money, request_info, section

# Choices only this form offers live here, not in the engine's shared options
VISIT_REASONS = ["معاينة قبل التركيب", "متابعة شكوى", "صيانة دورية"]

SECTIONS = [
    request_info("تاريخ الزيارة"),
    section(
        "بيانات الزيارة",
        f("reason", "سبب الزيارة", "select", True, options=VISIT_REASONS),
        f("technician_name", "اسم الفني", "staff", True),
        f("notes_for_team", "ملاحظات للفريق", "textarea"),
        note="تظهر الملاحظات للفني في أمر الزيارة.",
    ),
    section("قيمة الزيارة", money("fee_amount", "قيمة الزيارة")),
    attachments(files("site_photos", "صور الموقع، إن توفرت")),
    NOTES,
]
```

### The builders

```python
f(name, label, type="text", required=False, **extra)   # one field
money(name, label, required=False, **extra)            # a dirham amount (number, min 0, money=True)
yes_no(name, label, required=True, **extra)            # نعم / لا
files(name, label, required=False, **extra)            # an upload field
section(title, *fields, note=None)                     # a section, with an optional note under it
need(condition)                                        # required=True, or required_if=<condition>
```

### Whole sections several forms share

Use these instead of rebuilding them — they keep the forms consistent and carry rules of their own:

| Builder | Gives you |
|---|---|
| `request_info(date_label, invoiced=False, source=True)` | the request date and مصدر الطلب. `invoiced=True` makes the source Daftra's own list; `source=False` leaves it out |
| `client(code_required, name_label, creates_client=False)` | phone, client code, name — and, with `creates_client=True`, the extra fields a brand-new Daftra client needs |
| `address(title, required=True)` | emirate, area, street, house, the map picker and the coordinates |
| `amounts(...)`, `discount_fields(label)` | the subtotal/discount/total block, with the totals computed |
| `payment(title, when=True, invoiced=False)` | payment method, treasury, date, reference |
| `attachments(*files)` | the المرفقات section |
| `original_refs()` | «الطلب الأصلي» references |
| `NOTES` | the final free-text section |

### Field types

| Type | |
|---|---|
| `text` (default), `textarea`, `number`, `date`, `phone`, `email` | the plain ones |
| `select`, `multiselect` | need `options=[...]`; add `dropdown=True` to force a drop-down over radio buttons |
| `files` | an upload field; `.pdf .jpg .jpeg .png .webp .heic .mp4 .mov .doc .docx`, 20 MB each |
| `staff` | a name from Daftra's active staff |
| `product`, `order_lines` | the catalog. `order_lines` is the full picker with quantities, prices and a subtotal. `items="maintenance_items"` narrows it to the catalog's maintenance items; `item_ids`/`item_labels` name the products a form offers by their Daftra id (اعمال اضافية); `item_prices` says what a line's price starts at, by Daftra id. A line field marked `line_price` holds the price of the line instead of the catalog (with `only_for`, only for those products; without it, every line), and `column=True` puts its box in the table's سعر الوحدة column rather than among the line's own fields (صيانة وتبديل) |
| `package_color`, `inscription` | the cooler-specific pickers |
| `auto_user` | filled with the submitter's name; not typed into |
| `daftra_order_source`, `daftra_treasury`, `daftra_client_category`, `daftra_client_invoice` | a drop-down from Daftra. The id is **checked against Daftra's list** when the request is submitted, and again when it is approved |

### Useful `extra` keys

```python
f("code", "كود العميل", required=True, pattern=r"^\d{1,6}$", pattern_message="أرقام فقط، حتى 6 خانات")
f("days", "مدة التركيب", "number", integer=True, min=1, max=365, unit="يومًا", placeholder="مثال: 15")
f("date", "التاريخ", "date", True, default="today", not_future=True)
f("fee", "القيمة", "number", required_if={"field": "coverage", "equals": "مدفوع"})
f("total", "الإجمالي", "number", computed=["subtotal_amount", "discount_amount"])
money("inscription_price", "سعر الكتابة", charge=True, beside="inscription")
```

Conditions take `{"field": ..., "equals" | "gt" | "not_in": ...}`. The engine's shared ones —
`PAID`, `DISCOUNTED`, `CASH_PAYMENT` — are already defined.

### Where choices live

- **More than one form offers it** → `form_engine/options.py`, exported from the engine's
  `__init__` (colours, payment methods, emirates, treasury-by-method).
- **Only this form offers it** → the form's own `definition.py`, as above.

### Validation happens twice, from one definition

`form_engine/validation.py` checks a submission against the definition on the server;
`frontend/src/modules/requests/validation.js` repeats the same checks in the browser for instant
feedback. **The server is the one that decides.** Prices are always looked up server-side, never
taken from the browser.

### A check the field rules cannot express

Put it in `hooks.py` as `validate`, and point the spec at it:

```python
def validate(data: dict, ctx) -> dict:
    """Return {field_name: message} for anything wrong; {} when all is well."""
    invoices = ctx.choices.get("daftra_client_invoice") or []
    chosen = next((i for i in invoices if i["id"] == data.get("invoice")), None)
    if chosen and data.get("paid_amount", 0) > chosen["unpaid"] + 0.005:
        return {"paid_amount": f"المبلغ أكبر من المتبقي على الفاتورة ({chosen['unpaid']:,.2f} درهم)"}
    return {}
```

`ctx` is a `CheckContext`: `ctx.db`, `ctx.user`, and `ctx.choices` — what the form's list fields
offered, by field type (a list that could not be loaded is simply absent). It runs **after** the
field rules, and its messages reach the screen beside the right field.

Only `balance_payment` has one today.

---

## What approving a form creates in Daftra

If approving the form should create something in Daftra, give it an `on_approve` in `hooks.py`.
Four forms have one — new_sale, contract_renewal, maintenance and balance_payment. This is
the part to be careful with: it writes real numbered documents into
the live account.

### The shape

```python
"""What makes طلب زيارة موقع different: what approving it creates in Daftra."""

from ...modules.invoicing import (ensure_invoice, finish, invoice_items, payment_inputs,
                                  reports_daftra_errors, sales_person)
from ...modules.clients import client_id, update_client


@reports_daftra_errors
def on_approve(ctx) -> dict:
    request, db, reviewer = ctx.request, ctx.db, ctx.reviewer
    data = request.data

    # 1. Everything that can be checked is checked before anything is sent
    items = invoice_items(data, db)
    staff_id = sales_person(request)
    paid, method = payment_inputs(data)

    # 2. The client, if this form can bring a new one
    if request.daftra_client_id is None:
        request.save_document("client", client_id(data, db))
    update_client(request.daftra_client_id, data)

    # 3. The invoice, then the receipt and both PDFs
    invoice = ensure_invoice(request, items, staff_id)
    return finish(request, invoice, paid, method, reviewer, db)
```

`ctx` is an `ApprovalContext`: `ctx.request`, `ctx.db`, `ctx.reviewer` (the approving manager, who
becomes the receipt's المستلم). The return value is a summary dict that goes into the activity log.

### The building blocks

From `modules.invoicing`:

| | |
|---|---|
| `invoice_items(data, db)` | the order lines as Daftra `InvoiceItem` rows, prices looked up here. Raises if a product is not linked to Daftra |
| `ensure_invoice(request, items, staff_id, notes="")` | the invoice — found again if it already exists, created if not |
| `ensure_payment(request, invoice, paid, method, reviewer)` | the receipt (سند قبض) |
| `finish(request, invoice, paid, method, reviewer, db)` | the usual tail: the payment, both PDFs, the summary |
| `ensure_work_order(request, invoice, reviewer, db)` | the installation work order, its custom fields and its PDF |
| `ensure_estimate(request, items, staff_id, notes="")`, `save_estimate_pdf(request, estimate, db)` | the offer (عرض سعر) and its PDF — what طلب عرض سعر creates instead of an invoice. No payment and no work order: Daftra records nothing against an estimate |
| `get_invoice(id)`, `get_estimate(id)`, `payment_of(request, invoice)` | reading back |
| `sales_person(request)` | the submitter's Daftra staff id; raises a readable error if they are not linked |
| `payment_inputs(data)` | the amount paid now and its Daftra payment-method key |
| `money(value)`, `marker(request)`, `TOTAL_TOLERANCE` | amounts, and the mark that finds a document again |
| `reports_daftra_errors` | **always decorate with this.** It turns any Daftra refusal into the `SyncError` the manager reads |

From `modules.clients`: `client_id`, `existing_client_id`, `known_client`, `update_client`,
`save_address`, `held_custom_fields`.

### Keeping what each step created

Approving is synchronous, so the manager sees at once whether Daftra took it. If a step fails, the
request **stays submitted** and whatever was already created is kept, so approving again carries on
from the step that failed instead of creating anything twice.

That is what `request_documents` is for — one row per request and kind:

```python
request.save_document("invoice", invoice_id, "06273")   # keeps the id and the number people read
request.doc_id("invoice")                               # Daftra's id, or None if that step has not run
request.doc_no("invoice")                               # "06273"
request.forget_document("invoice")                      # this one turned out not to be ours
```

Kinds in use: `client`, `invoice`, `payment`, `work_order`, `estimate`. **A new kind needs no
migration** — `estimate`, which طلب عرض سعر saves, was added as `save_document("estimate", …)` and
nothing else; a credit note for a return would be the same.

There are also read-only shorthands the API and the screens use: `request.daftra_invoice_id`,
`daftra_invoice_no`, `daftra_receipt_no`, `daftra_work_order_no`, … They read the documents table.

If an id was lost because the answer never arrived, the invoice is found again by its `po_number`
and the payment by its notes, both `<DAFTRA_MARKER_PREFIX>-<request id>` — which is why each portal
sharing one Daftra account needs its own prefix.

### Writing it safely

**Never develop this against the live account.** `DAFTRA_FAKE=true` is the default locally: a
stand-in inside the portal answers every call, seeded from your own database, with its own
persisted store. Fill the form, approve it, open the PDFs, make a step fail and approve again:

```
docker compose exec backend python -m app.jobs fake_daftra calls                                  # what Daftra would have received
docker compose exec backend python -m app.jobs fake_daftra fail-once /api2/invoice_payments.json  # fail midway, then retry
```

**Pin the payload with a test.** The most valuable tests in the repo are the ones asserting exactly
what Daftra receives for each invoiced form — they are what let the whole codebase be rearranged
without changing a single byte sent to Daftra. Put yours in `tests/forms/<key>/`, in the style of
`tests/modules/requests/test_review.py`:

```python
[invoice] = fake_daftra.posted("/api2/invoices.json")
assert invoice["Invoice"]["client_id"] == 4053
assert invoice["InvoiceItem"][0]["unit_price"] == 1000
```

**If the fake does not know a call**, teach it: add a route to
`integrations/daftra/fake.py`'s `routes()`. Keep what it knows about how Daftra really behaves —
a client save refused without its custom fields, the order-source edit that adds a copy — since
that is the point of it.

**A pass on the fake does not prove Daftra accepts it.** Before merging anything that changes what
is sent, run it once with `DAFTRA_FAKE=false` against test records. When the live account shows a
new quirk, add it to the fake.

---

## Adding other things

### A field type the engine lacks

Add it to `form_engine` (the builder, the validation, and the input in
`frontend/src/modules/requests/form/fields.jsx`), never to one form. Then every form can use it.

### A module

A folder under `app/modules/` with only the files it needs, a `__init__.py` listing its public
names, its router mounted in `main.py`, and its models imported by `modules/models.py`. Keep the
dependency pointing one way; if it seems to need a module that needs it, see
[When two modules seem to need each other](#when-two-modules-seem-to-need-each-other).

### A job

Anything that runs outside a page — a nightly sync, a button on the «المزامنة مع دفترة» page, a
command-line import — is a job in `app/jobs/`:

```python
from ..modules import clients
from .registry import job


@job("sync_clients", label="العملاء", on_admin_page=True,
     about="Brings clients and addresses in step with Daftra")
def sync_clients(db, who) -> dict:
    return clients.sync_from_daftra(db, daftra.list_clients())
```

Add it to `jobs/__init__.py`'s imports and `JOBS`. **A job holds no business rules** — it calls a
module's service, so the page, the cron and `python -m app.jobs <name>` all run the same code, and
every run is recorded in `job_runs`. `on_admin_page=True` puts it on the sync page with a button;
`recorded=False` is for things not worth a row, like the startup cache warm-up.

### A Daftra call

One function in `integrations/daftra/resources.py`, named after what it does in Daftra, exported
from the package's `__init__`. Nothing above it writes a Daftra path. If the result is a list that
changes rarely, wrap it in `cache.cached(...)`. Then add the route to `fake.py` so tests and local
work keep going.

### An admin page

Add it to `MENU` in `core/permissions.py` (key, label, path) — that is also what declares its
permission — then a screen in `frontend/src/app/routes.jsx` keyed the same way. Protect its routes
with `require("<key>")`. If only an admin may ever hold it, add the key to `ADMIN_ONLY`.

### A migration

Alembic, in `backend/alembic/versions/`, numbered in sequence. **Expand, then contract**:
`portal-deploy` can put the old code back but not the database, so a release never removes or
renames anything the release before it reads. Add the new thing and copy into it; the next release,
once the first is confirmed live, removes the old one. Migrations 0019–0021 each carry a note
saying what the next release must drop.

---

## What the tests enforce

```
sh backend/run-tests.sh      pyflakes, then every backend test (Docker, against portal_test)
sh frontend/check.sh         the frontend tests and a production build
sh frontend/ui-check/run.sh  a real browser over the running stack, desktop and phone widths
```

Run all three before pushing. Beyond the ordinary tests, a few guard the shape itself:

| Test | Catches |
|---|---|
| `tests/test_architecture.py` | an import that goes up a layer, reaches inside another module, or closes a circle |
| `tests/forms/test_form_registry.py` | a renamed or missing form key, a form with no label/icon/sections, a `daftra_note` that disagrees with `on_approve` |
| `tests/modules/identity/test_per_form_access.py` | each access rule, one test per rule |
| `tests/modules/invoicing/test_invoicing.py` | our payment methods still matching the forms' choices |
| the payload tests in `tests/modules/requests/test_review.py` | any change in what Daftra receives |
| `test_lists_load_in_a_fixed_number_of_queries` | an N+1 creeping into a list endpoint |

The architecture test is not decoration: during the refactor it caught three real violations —
a `core`→`modules` layer jump, one module querying another's table, and an `audit`↔`identity`
import cycle — each of which would have been invisible in review.
