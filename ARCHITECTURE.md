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

**Forms are plugins.** Each of the 20 forms is a folder under `app/forms/<key>/` holding what it
asks (`fields.py`, one switch per field) and, when approving it creates something in Daftra, what
it sends there (`output.py`, one function per document). Nothing outside that folder names
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
│   ├── terms/                   الشروط والأحكام: versioned texts, and the one each package prints
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
│   ├── catalog/ (with Terms.jsx: its terms tab) · lookups/ · audit/ · notifications/ · system/
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
forms/balance_payment/output.py                the form: what goes in each document it sends
modules/invoicing/runner.py                    builds them all, then makes them in order
modules/invoicing/invoice.py                   the steps: the payment, the receipt, the PDFs
                                               (estimate.py for the offer طلب عرض سعر makes)
integrations/daftra/resources.py → client.py   the Daftra client
  → live.py (the HTTP call) or fake.py         DAFTRA_FAKE decides
```

Read it the other way to see the rule: every arrow points downwards, and `requests` never names a
form or imports `invoicing`.

---

## Adding a form

Twenty forms exist (7 visible, 13 hidden); another is a folder and one line. **No router, table, migration or
frontend change.**

### 1. The folder

```
app/forms/<key>/
├── __init__.py      the FormSpec — what the form is
├── fields.py        what it asks: its sections, one switch per field
└── output.py        only if approving it creates something in Daftra: one function per document
```

The **key is stored on every request made with that form, so it may never be renamed.** Pick it
once, in `snake_case`. `tests/test_architecture.py` holds every folder to this shape: `fields.py`
always, `output.py` exactly when the form has an `on_approve`.

### 2. The `FormSpec`

`app/forms/site_visit/__init__.py`:

```python
from ...modules.form_engine import FormSpec, register

from . import fields, output

register(FormSpec(
    key="site_visit",                # stored on every request: never rename
    label="طلب زيارة موقع",
    icon="map-pin",                  # any name from the design system's icon set
    description="تسجيل طلب زيارة موقع",
    sections=fields.SECTIONS,
    visible=True,                    # False: no new requests; old ones still open and reviewable
    daftra_note="ويُنشأ في دفترة ...",  # only if approving creates something there
    validate=fields.validate,        # optional: a check the field rules cannot express
    on_approve=output.on_approve,    # optional: what approving creates in Daftra
))
```

A form that creates nothing in Daftra has no `output.py`, and its `__init__` imports just `fields`.

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

`fields.py` holds `SECTIONS`. Each section is a function with **one keyword argument per field**,
and each argument is a switch:

| Switch | |
|---|---|
| `HIDE` | not on this form at all |
| `SHOW` | on the form, may be left empty |
| `REQUIRED` | on the form, must be filled |
| `REQUIRED_IF(when)` | must be filled when `when` holds, e.g. `REQUIRED_IF(PAID)` |
| `NEW_CLIENT(switch)` | as `switch`, but only while the phone search has found no client |

Every field of a section must be named — the arguments have no defaults — so a form that forgets
one, or misspells one, fails when the app starts rather than when someone opens it. What a field
*is* (its type, pattern, how it is computed) stays inside the section: a form decides whether it
appears and whether it must be filled.

```python
"""What طلب زيارة موقع asks: its sections, with one switch per field."""

from ...modules.form_engine import HIDE, REQUIRED, SHOW, f, files, money, shared, switched

# Choices only this form offers live here, not in the engine's shared options
VISIT_REASONS = ["معاينة قبل التركيب", "متابعة شكوى", "صيانة دورية"]


def visit(*, reason, technician_name, notes_for_team):
    """This form's own section: a function like the shared ones, written here."""
    return switched(
        "بيانات الزيارة",
        (reason, f("reason", "سبب الزيارة", "select", options=VISIT_REASONS)),
        (technician_name, f("technician_name", "اسم الفني", "staff")),
        (notes_for_team, f("notes_for_team", "ملاحظات للفريق", "textarea")),
        note="تظهر الملاحظات للفني في أمر الزيارة.",
    )


SECTIONS = [
    shared.request_info(request_date=REQUIRED, employee_name=SHOW, order_source=HIDE, source=REQUIRED,
                        labels={"request_date": "تاريخ الزيارة"}),
    visit(reason=REQUIRED, technician_name=REQUIRED, notes_for_team=SHOW),
    switched("المرفقات", (SHOW, files("site_photos", "صور الموقع، إن توفرت"))),
    shared.notes(notes=SHOW),
]
```

`shared.x` is a section many forms use; a plain function is the form's own. Every form's sections
are pinned by `tests/forms/snapshots/<key>.json` — the JSON the browser is sent — so a change to
what a form asks shows in review as a change to its snapshot, rewritten on purpose:

```
./run-tests.sh tests/forms/test_fields_snapshot.py --update-snapshots
```

### The shared sections

From `form_engine/sections.py`, reached as `shared.x(...)`. Each also takes `labels={field: text}`
for what a field is called on this form, and `note=`.

| Section | Its fields |
|---|---|
| `shared.request_info` | `request_date`, `employee_name`, `order_source` (Daftra's list), `source` (the portal's) |
| `shared.client` | `phone`, `phone2`, `client_code`, `customer_name`, `customer_type`, `gender`, `email` — and `placeholders=` |
| `shared.address` | `category`, `area`, `emirate`, `street`, `house`, `location_url`, `coordinates` — and `title=` |
| `shared.amounts` | `subtotal_amount`, `total_amount`, `discount_label`, `discount_amount`, `discount_approved_by`, `paid_amount`, `remaining_amount`, `remaining_due_date` — and `must_pay=`, `price_default=`, `paid_default=` |
| `shared.payment` | `payment_method`, `treasury`, `payment_date`, `payment_reference`, `collector_name` — and `title=` |
| `shared.notes` | `notes` |

In `shared.amounts` an amount the form works out is `SHOW` and one the salesperson types is
`REQUIRED`: `subtotal_amount=SHOW` is the order lines' total, `=REQUIRED` a price typed in. A
combination nothing can be worked out from (a remainder with no amount paid) is refused when the
form loads. Two labels follow the switch rather than the form, because they say whether the field
must be filled: «كود العميل» / «كود العميل، إن وجد», and the due date of what is left.

### The builders, for a form's own sections

```python
switched(title, *(switch, field), note=None)           # a section from switched fields
switched_fields(*(switch, field))                      # the same, as a list: an order line's line_fields
f(name, label, type="text", **extra)                   # one field
money(name, label, **extra)                            # a dirham amount (number, min 0, money=True)
yes_no(name, label, **extra)                           # نعم / لا
files(name, label, **extra)                            # an upload field
original_refs()                                        # the three «الطلب الأصلي» reference fields
```

A field built here leaves `required` to its switch, so write none on it.

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
- **Only this form offers it** → the form's own `fields.py`, as above.

### Validation happens twice, from one set of fields

`form_engine/validation.py` checks a submission against the definition on the server;
`frontend/src/modules/requests/validation.js` repeats the same checks in the browser for instant
feedback. **The server is the one that decides.** Prices are always looked up server-side, never
taken from the browser.

### A check the field rules cannot express

It is a rule about the form's fields, so it goes in `fields.py` as `validate`, and the spec points at it:

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

If approving the form should create something in Daftra, give it an `output.py`. Seven forms have
one — new_sale, online_sale, contract_renewal, maintenance, balance_payment, quotation and
tech_extra_works. This is the part to be careful with: it writes real numbered documents into the
live account.

### The shape

One function per document, each returning what goes into it field by field — or `None` when this
request has none — and the list they are made in:

```python
"""What approving طلب زيارة موقع sends to Daftra."""

from ...core.text import squash
from ...modules.invoicing import (ClientRecord, Invoice, Receipt, approve, money, order_lines, package_terms,
                                  sales_person, service_address)


def client(ctx):
    d = ctx.data
    return ClientRecord(phone=d.get("phone"), client_code=d.get("client_code"), name=d.get("customer_name"),
                        if_unknown="create", keep_in_step=True)


def invoice(ctx):
    d = ctx.data
    return Invoice(
        items=order_lines(ctx),                  # raises, before anything is sent, for an unlinked product
        sales_person=sales_person(ctx.request),  # raises for a salesperson not linked to Daftra
        date=d.get("request_date"),
        total=d.get("total_amount"),             # what Daftra's total must come to
        address=service_address(d),
        terms=package_terms(ctx),
    )


def receipt(ctx):
    d = ctx.data
    if money(d.get("paid_amount")) <= 0:
        return None                              # nothing paid: no receipt
    return Receipt(amount=d.get("paid_amount"), method=d.get("payment_method") or "",
                   treasury=d.get("treasury"), date=d.get("payment_date"),
                   received_by=sales_person(ctx.request), client_name=squash(d.get("customer_name")))


DOCUMENTS = [client, invoice, receipt]
on_approve = approve(DOCUMENTS)
```

`ctx` is an `ApprovalContext`: `ctx.data` (the request's fields), `ctx.request`, `ctx.db`,
`ctx.reviewer` (the approving manager).

**Every function is called before anything is sent**, so a check one makes — an unlinked product,
an unknown payment method — stops the approval before the client is created. Then the documents
are made in the order of `DOCUMENTS`. A `Receipt` pays the `Invoice` (or `ExistingInvoice`) just
before it; a `WorkOrder` and an `InvoiceEmail` need an invoice before them. The invoice's PDF is
taken after its receipt, because Daftra draws it as it stands.

`tests/forms/test_fields_and_output_agree.py` reads each `output.py` and fails when it reads a
field its `fields.py` does not show — so hiding a field the receipt needs fails in a test, not at
اعتماد. A field read only for requests an earlier version of the form wrote is listed in that
form's `LEGACY_FIELDS`.

### The documents

From `modules.invoicing` (`documents.py`). The form decides every field; what no form should repeat
— making each once however often it is approved, `is_offline`, store, branch, tax, the total check,
the PDFs — the engine does.

| | |
|---|---|
| `ClientRecord` | العميل, found by code or phone. `if_unknown="create"` makes it; any other text is the error shown. `keep_in_step` puts what the form says on a known client |
| `Invoice` | الفاتورة: `items`, `sales_person`, `date`, `total`, `discount`, `discount_label`, `order_source`, `address`, `terms`. Sends no «notes»: Daftra shows them under الشروط والأحكام |
| `Estimate` | عرض السعر: an invoice's fields, and `notes`. No receipt and no work order go with it |
| `ExistingInvoice` | an invoice Daftra already has, for the receipt after it to pay (طلب تسديد مبلغ متبقي) |
| `Receipt` | سند القبض: `amount`, `method` (the form's word, turned into Daftra's key), `treasury`, `date`, `reference`, `received_by`, `notes` |
| `WorkOrder` | أمر الشغل: `title`, `days`, `description`, `fields` (its custom fields by name), `printed` (what the PDF prints) |
| `InvoiceEmail` | the invoice emailed by the portal — Daftra sends nothing through the API |

And what they are built from: `order_lines(ctx)`, `service_address(data)`, `package_terms(ctx)`,
`installation_work_order(request, db)` (the cooler's work order, worked out from the order lines),
`sales_person(request)`, `form_notes(data, *parts)`, `money(value)`.

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
