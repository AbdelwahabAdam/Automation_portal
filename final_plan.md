# Modular monolith refactor: the final plan

Agreed on 2026-10-30. Nothing here has been built yet.

The portal stays one app, one database and one deploy. Its code is reorganised into modules by business area,
and every form becomes its own folder. Phases 0–6 move code without changing what anyone sees (one exception,
the client-sync fix in phase 5); phases 7–9 change behaviour and say how. Every phase keeps all the tests green
and can be merged and deployed on its own.

1. What we agreed
2. Before starting
3. Target structure
4. Rules
5. Forms as plugins
6. Per-form access
7. The Daftra client, its fake, and the customers module
8. Jobs
9. Frontend
10. Daftra documents table
11. Phases
12. Risks
13. Done when
14. Adding a form afterwards
- Appendix A: where every file goes
- Appendix B: what the final code looks like

---

## 1. What we agreed

| | Decision |
|---|---|
| Architecture | Modular monolith, with modules by business area (identity, requests, invoicing, clients, catalog, …), not one module per form |
| Forms | Each form is a plugin folder, `app/forms/<key>/`: its fields, plus hooks only where it differs (extra checks, what approving creates in Daftra). All 19 forms — the 5 visible and the 14 hidden — and every future one |
| Access | Set explicitly on every form by the admin: who can fill it, who can see all its requests, who can review it. No implicit rule: department managers (`users.manages`) are moved into roles and removed. A new form is closed to everyone but admins until access is granted |
| Admin pages | Each has its own permission and can be put in a role, except users and roles, which stay admin-only |
| Menu | The «المبيعات» group becomes «الطلبات», since the forms are no longer sales-only |
| Daftra client | `app/integrations/daftra/`: talks to Daftra's API and nothing else |
| Fake Daftra | `DAFTRA_FAKE=true` in `.env` swaps the real Daftra for a stand-in inside the portal, so the whole flow can be tested locally without touching the live account. On by default locally; it cannot run on the server (§7) |
| Portal client | `app/modules/clients/`: the portal's customers — the local copy of Daftra's clients, lookup by phone or code, addresses, categories, the nightly sync, creating a client in Daftra |
| Jobs | `app/jobs/`: one runner, and every run recorded |
| Module layers | `__init__.py` (the public API), `models.py`, `schemas.py`, `repo.py`, `service.py`, `router.py` (transport) — only the ones a module needs |
| Also in | Frontend restructure; a URL for every form and request; a table for the Daftra documents a request creates |
| Not in | Creating the Daftra documents in the background. Approving stays synchronous, so the manager sees at once whether Daftra took it |

---

## 2. Before starting

- **Commit what is in progress.** 26 files are changed but not committed (the Daftra sync, the forms, their tests,
  the request form). Moving files on top of them would make both changes unreviewable.
- **Work on a branch** (e.g. `refactor/modular`) and merge each phase to `main` when its checks pass. A push to
  `main` deploys to the live server, so nothing half-done may reach it.
- **Back up the database before every phase with a migration** (5, 7, 9), as the `db-backup-before-*.sql` files
  did before, and try the migration on a copy of the live data first.
- **Hold the `enhancementv2.md` items (6–12) until phase 8 is done.** 8 (menu counts) and 11 (home page) depend
  on who may see what, which phase 7 changes; 6, 7, 9 and 10 edit files that phases 4 and 6 move.

---

## 3. Target structure

### Backend

```
backend/app/
├── main.py                      # builds the app: mounts the routers, maps errors, starts the cache warm-up
├── core/                        # shared by everything; no business rules
│   ├── config.py                # settings (today's config.py)
│   ├── database.py              # engine, Session, Base, get_db, run_migrations
│   ├── security.py              # token, password hashing, current_user, require("<permission>")
│   ├── permissions.py           # the registry every module and form declares its permissions in
│   ├── errors.py                # NotFound, Conflict, Forbidden, Invalid, ExternalFailure
│   ├── context.py               # Actor: who is acting and from where (user, ip, user agent)
│   └── text.py                  # Arabic digits, UAE time, phone numbers
├── integrations/
│   └── daftra/                  # the Daftra client
│       ├── client.py            # the one switch: hands every call to live or fake (DAFTRA_FAKE)
│       ├── live.py              # HTTP: calls, retries, error messages, file upload, invoice PDF
│       ├── fake.py              # the stand-in: the same three calls, no network (moved from tests/)
│       ├── resources.py         # one function per Daftra call the portal makes
│       └── cache.py             # the cached lists (staff, treasuries, order sources, categories)
├── modules/
│   ├── identity/                # login, two-step codes, password links, account, users, roles
│   ├── audit/                   # the activity log and its page
│   ├── notifications/           # email: sending, templates, the test page
│   ├── form_engine/             # FormSpec, the registry, field builders, shared choices, validation
│   ├── requests/                # drafts, submitting, attachments, history, review, the Daftra documents
│   ├── invoicing/               # what approving creates in Daftra (today's daftra_sync), the portal's PDFs
│   ├── clients/                 # the customers — "the client for the portal"
│   ├── catalog/                 # products and packages
│   ├── lookups/                 # Daftra's staff, treasuries and order sources (+ the order sources page)
│   ├── system/                  # version
│   └── models.py                # imports every module's models, for SQLAlchemy and Alembic
├── forms/                       # one folder per form
│   ├── __init__.py              # imports every form, which registers it
│   ├── new_sale/                # __init__.py · definition.py · hooks.py
│   ├── contract_renewal/        # __init__.py · definition.py · hooks.py
│   ├── maintenance/             # __init__.py · definition.py · hooks.py
│   ├── balance_payment/         # __init__.py · definition.py · hooks.py
│   ├── tech_extra_works/        # __init__.py · definition.py · hooks.py
│   └── quotation/ …             # the other 14: __init__.py · definition.py
└── jobs/                        # python -m app.jobs <name>   (see §8)
```

Each module has the files it needs and no more:

| Module | `__init__` | `models` (its tables) | `schemas` | `repo` | `service` | `router` |
|---|---|---|---|---|---|---|
| identity | ✓ | users, roles, user_roles | ✓ | ✓ | ✓ | ✓ |
| audit | ✓ | audit_log | ✓ | ✓ | ✓ | ✓ |
| notifications | ✓ | | ✓ | | ✓ | ✓ |
| form_engine | ✓ | | | | ✓ (validation) | |
| requests | ✓ | requests, attachments, request_events, request_documents | ✓ | ✓ | ✓ | ✓ |
| invoicing | ✓ | | | | ✓ | |
| clients | ✓ | clients, addresses, client_categories | ✓ | ✓ | ✓ | ✓ |
| catalog | ✓ | products, packages, product_to_package | ✓ | ✓ | ✓ | ✓ |
| lookups | ✓ | | ✓ | | ✓ | ✓ |
| system | ✓ | | | | | ✓ |

The frontend is in §9. Appendix B has the full tree, file by file, and the code of one module and one form.

### Words

- "client" alone means a customer, as in Daftra and the `clients` table. The code that calls Daftra's API is
  always "the Daftra client" (`integrations/daftra`).
- `invoicing` is today's `daftra_sync`. The new name also ends the mix-up with `daftra_refresh` that the README
  warns about.

---

## 4. Rules

### Which way imports go

```
main.py · jobs/            entry points
      ↓
forms/<key>/               the forms
      ↓
modules/<module>/          business areas: each other only through __init__.py, never in a circle
      ↓
integrations/daftra/       knows nothing about modules or forms
      ↓
core/                      knows nothing above it
```

A file imports from its own level or below, never above, and from another module only through its
`__init__.py`. Today two imports go the wrong way: the Daftra client imports the forms package (`daftra.py:17`,
for the payment methods), and the work-order step imports helpers of the new-sale form
(`daftra_sync/work_order.py:12`).

**A test enforces it.** `tests/test_architecture.py` reads every import with Python's `ast` module and fails
when:
- an import goes up a level;
- a module reaches into another module's files (`from app.modules.catalog.repo import …`) instead of its
  `__init__`;
- two modules import each other, directly or through others.

import-linter can check the levels but not "only through `__init__`", so one small test does all three with no
new tool. It runs wherever the tests run: `run-tests.sh` and CI. It allows `modules/models.py` to import every
module's models (that is its job), and `main.py` and `jobs/` to import anything.

### Inside a module

| File | Holds | Never |
|---|---|---|
| `__init__.py` | what other modules may use: re-exported functions, classes, errors | logic of its own |
| `router.py` | the HTTP routes: read the input, call the service, return the answer | query the database, decide business rules, commit |
| `schemas.py` | the Pydantic shapes of what comes in and goes out | touch the database |
| `service.py` | the business rules, one function per thing a user or job does; commits | raise `HTTPException` or know it is behind HTTP |
| `repo.py` | the SQLAlchemy queries on this module's own tables, as plain functions | commit, call other modules, decide anything |
| `models.py` | this module's tables | `relationship()` to another module's model, except `User` |

- **A layer that outgrows one file splits by topic**, into a folder of the same name (`identity/service/auth.py`,
  `identity/service/users.py`, …) or a sibling file (`clients/in_daftra.py`). What it splits into is still that
  layer and follows that layer's rules. `identity` and `requests` start this way, since each would otherwise have
  a service of several hundred lines.
- **A module owns its tables.** Only its own code writes them; everyone else goes through its `__init__`.
  Foreign keys across modules are fine.
- **No generic `BaseRepository`.** SQLAlchemy's session already is one. A repo function exists because a query
  has a name worth giving it.
- **Errors.** Services raise the errors in `core/errors.py`. One handler in `main.py` turns them into
  404 / 409 / 403 / 422 / 502 with the same body as today — `{"detail": "<message>"}`, or
  `{"detail": {"errors": {...}}}` for form errors — so the frontend reads them unchanged. This is what lets a job
  call the same service a page does.
- **Who is acting.** Routers pass an `Actor` (user, ip, user agent) into the services instead of FastAPI's
  request, and the activity log reads it from there. Jobs pass the system actor («المزامنة الليلية»).
- **Login checks without a circle.** `core/security.py` decodes the token and asks a loader that `identity`
  registers at startup for the user. So every module can `require("…")` from `core` without importing
  `identity`, and `identity` can still write to the activity log.

---

## 5. Forms as plugins

### What a form folder holds

```python
# app/forms/balance_payment/__init__.py
from app.modules.form_engine import FormSpec, register
from . import definition, hooks

register(FormSpec(
    key="balance_payment",               # stored on every request: never rename
    label="طلب تسديد مبلغ متبقي",
    icon="send",                         # from frontend/src/formsMeta.js, which goes away
    description="سداد المبلغ المتبقي على طلب",
    sections=definition.SECTIONS,        # built with form_engine's field builders, as today
    visible=True,                        # False: no new requests; old ones still open and can be reviewed
    daftra_note="ويُنشأ في دفترة سند قبض بالمبلغ المدفوع على الفاتورة المختارة.",
    validate=hooks.validate,             # optional: checks the field rules cannot express
    on_approve=hooks.on_approve,         # optional: what approving creates outside the portal
))
```

- **`definition.py`** — the sections and fields, moved as they are from `forms/definitions.py`. Choices only this
  form uses move here from `options.py` (the technical services of tech_extra_works, the devices and services of
  maintenance, the renewal price, …). Shared ones (colours, payment methods, emirates, treasury by method) stay in
  `form_engine/options.py`.
- **`hooks.py`** — only where the form differs:

| Form | `validate` | `on_approve` (today's function) |
|---|---|---|
| new_sale | | client if new, invoice, receipt, work order when asked (`sync_new_sale`) |
| contract_renewal | | client's category, renewal invoice, receipt (`sync_contract_renewal`) |
| maintenance | | client if new, invoice of the items, receipt (`sync_maintenance`) |
| balance_payment | paid ≤ unpaid on the chosen invoice (moved out of the shared `requests_api.apply_action`) | receipt on the chosen invoice (`sync_balance_payment`) |
| tech_extra_works | | invoice of the works, receipt (`sync_tech_extra_works`) |
| the other 14 | | |

- The work order's custom fields (`WORK_ORDER_FIELDS`: colours, inscription, cover back, …) are read from
  new_sale's data, so that mapping moves to `forms/new_sale/`. `invoicing.ensure_work_order` takes the values it
  should write.
- tech_extra_works has no icon or description today (it is missing from `formsMeta.js` and shows the default
  icon). Pick them when its folder is made.

### What the engine does with it

- `GET /api/form-types` returns every form with its icon, description, `daftra_note`, `invoiced` (true when it has
  `on_approve`; `RequestView.jsx` reads it) and what this user may do with it (§6).
- Submitting runs the field rules, then the form's `validate`.
- Approving runs the form's `on_approve` inside the row lock, exactly as `daftra_sync.sync` does today. Each id is
  kept on the request as its step succeeds, approving again carries on from the step that failed, and the manager
  sees why it failed.
- The engine never names a form: a search for a form key outside `app/forms/` finds nothing (tests and migrations
  aside).

### Why not a full module per form

All 19 forms share one table, one lifecycle, one validator and one review queue, and the frontend draws every one
of them from its definition. Five layers per form would make about 95 files of pass-throughs. The review queue
would have to reach into 19 modules, and a change to the lifecycle would need 19 edits.

---

## 6. Per-form access

### The permissions

Every form has three, made from its key; nobody writes them by hand:

| Permission | Lets the user |
|---|---|
| `form.<key>.submit` | see the form in النماذج, fill it, save drafts, submit, correct their own returned requests |
| `form.<key>.view` | see everyone's requests of this form, with their files, without changing them |
| `form.<key>.review` | see them in المراجعة and approve or return them (includes view) |

The admin pages get one each: `admin.users`, `admin.roles`, `admin.audit`, `admin.catalog`, `admin.sync`,
`admin.order_sources`, `admin.mail`. `admin.users` and `admin.roles` stay admin-only, because whoever holds them
could give themselves anything. The others can be put in a role, e.g. someone who keeps the catalog without being
an admin.

A role is a set of these keys. A user has the keys of all their roles. An admin (`is_admin`) has every key, as
today.

### Rules

- **A new form is closed.** Only admins see it until an admin grants `form.<key>.submit` to a role. Its three
  keys show up in the roles screen by themselves.
- A hidden form (`visible=False`) takes no new requests; view and review still work on its old ones.
- Nobody decides on their own request, except an admin (as today).
- The owner can always open their own requests, even after losing `submit`. They can change a draft only while
  they still hold `submit` for that form.
- The lookups the forms use (client search, products, Daftra's lists) are open to anyone holding any form
  permission.
- The server checks every call: opening a form, creating, saving, submitting, uploading, viewing, deciding.
  Hiding a button is never the check.

### Pages, built from the permissions

| Page | Shown when the user holds | Shows |
|---|---|---|
| النماذج | any `.submit` | only the forms they may fill |
| طلباتي | any `.submit`, or has requests of their own | their own requests |
| المراجعة | any `.view` or `.review` | requests of those forms; approve and return only with `.review` |
| each admin page | its permission | |

The «المبيعات» group in the menu becomes «الطلبات», since the forms are no longer sales-only (a technician's
النماذج would otherwise sit under المبيعات).

### Where the admin sets it

الإدارة ← الأدوار والصلاحيات gets two tabs over the same data:
- **الأدوار** — one role at a time: a row per form with three boxes (تعبئة · عرض · مراجعة), then the admin pages.
- **النماذج** — one form at a time: which roles can fill it, see it and review it. This is "on every form, add who
  can access it".

The users screen and the account page lose «يدير الأقسام».

### Moving today's access across: nobody gains or loses anything on the day

- A role with `sales.new_request` or `sales.my_requests` gets `form.<key>.submit` for each of the 5 visible forms
  (today those pages open all of them).
- Users who manage `sales` get a new role, «مراجعة جميع النماذج», with `review` on all 19 forms and `submit` on
  the 5 visible ones (today a manager opens every sales page, and المراجعة shows every form).
- The pages of the hidden departments (`data_entry.home`, `accounting.home`, `operations.home`) are dropped;
  nobody could open them.
- The admin then narrows the roles, e.g. a technicians' role with only tech_extra_works.
- Old activity-log entries keep their old page keys, and their labels stay so they still read.

---

## 7. The Daftra client, its fake, and the customers module

### `integrations/daftra` — the Daftra client

Everything in today's `daftra.py` that is about talking to Daftra: the calls and their retries, Daftra's error
messages, the file upload, the sign-in the invoice PDF needs, paging through lists, the cached lists. One function
per call the portal makes (`resources.py`), named after what it does in Daftra.

It knows nothing about forms, requests, our tables or our wording. What leaves it:
- address parsing, the city table and the categories' locations → `clients`;
- `PAYMENT_METHOD_KEYS` (our payment methods as Daftra's keys) → `invoicing`;
- `open_invoices` and `invoice_label` (which of a client's invoices still have money due, and how one reads in
  a drop-down) → `clients`, since both the client-details route and the invoice field use them.

The tests use the fake below. The payload tests keep their assertions: they are the proof that Daftra receives
exactly what it did before.

### The fake Daftra client

**What it is for.** Trying the whole flow on a local machine: fill a form, approve it, open the invoice, receipt and
work order, fail midway and approve again. Today that means real numbered invoices on the live account, deleted by
hand afterwards.

**The switch.** One setting, in the `.env` next to `docker-compose.yml`:

```
DAFTRA_FAKE=true     # the stand-in: nothing reaches Daftra, and no Daftra key is needed
DAFTRA_FAKE=false    # the live account, with DAFTRA_SUBDOMAIN and DAFTRA_API_KEY
```

Apply a change with `docker compose up -d backend`; `docker compose restart` keeps the old value. Locally it is on
unless set to `false` (`DAFTRA_FAKE: ${DAFTRA_FAKE:-true}` in `docker-compose.yml`), so a portal on someone's machine
cannot write to the live account by accident. In the code the default is `false`.

**How it plugs in.** Everything that reaches Daftra's network goes through three functions: `call`, `upload_file` and
`invoice_pdf`, the same three `conftest.py` replaces today. `live.py` and `fake.py` both offer them, and `client.py`
picks one. Nothing above it knows which it got.

```python
# integrations/daftra/client.py
def _backend():
    return fake if settings.daftra_fake else live


def call(method: str, path: str, params: dict | None = None, body: dict | list | None = None) -> dict:
    return _backend().call(method, path, params, body)

# upload_file and invoice_pdf the same way
```

**One fake, for tests and for local use.** `tests/fake_daftra.py` moves to `integrations/daftra/fake.py`. It has to:
`.dockerignore` leaves `tests/` out of the image. It keeps what it knows about how Daftra behaves (a client save
refused without its custom fields, the name rebuilt from the name fields, the order-source edit that adds a copy).
Tests use it in memory, with a new account per test and the helpers they have now (`calls`, `posted`, `fail_once`).

**What local use adds:**

| Need | What the fake does |
|---|---|
| Keep its data across restarts, and share it between the server and a command | Saves to `uploads/fake_daftra.json` in the uploads volume (gitignored, since it holds client data), replacing the file whole after each write. Otherwise a restart forgets invoices that requests still point at |
| Know the clients the local database knows | Is seeded from the local database on every start, adding what is missing: clients with their addresses and the custom fields our account requires, products linked to Daftra, categories, and the staff linked to users. Otherwise approving for an existing client fails, because the fake has never seen its Daftra id. With no local clients it adds a few samples, which a client sync brings in |
| Answer every call the portal makes | Adds the client categories list, and listing all clients (today's search compares whole words, so a listing skips any client with a second phone) |
| Offer what the forms expect | Starts with the treasuries `TREASURY_BY_METHOD` names (13, 9, 16, 7, 8, 12), a few staff and the order sources, since submitting checks ids against these lists |
| Give PDFs that open | Draws a simple invoice PDF with weasyprint, marked «فاتورة تجريبية». Tests keep their stub |
| Say when it does not know a call | Refuses with a `DaftraError` naming the call, which the manager sees. In tests it still fails the test outright |
| Never be confused with the real account | Its ids start at 900000001, so a fake id that reaches the live account finds nothing rather than a real record. Client numbers stay six digits (from 900001), because the forms check that |

The seed reads the database, so it lives with the commands in `jobs/fake_daftra.py` and hands the fake plain data;
`integrations/` still imports no module.

**Commands.** Run them with `docker compose exec backend`. They refuse unless `DAFTRA_FAKE` is on.

```
python -m app.jobs fake_daftra calls                                  # the last 20 calls: what Daftra would have received
python -m app.jobs fake_daftra fail-once /api2/invoice_payments.json  # that call fails once, to try approving again
python -m app.jobs fake_daftra seed                                   # add what the local database has gained since the start
python -m app.jobs fake_daftra reset                                  # forget everything; the next start seeds it again
```

The file keeps the last 500 calls. Daftra's lists stay cached for up to 15 minutes, so `docker compose restart backend`
shows a change at once.

**It cannot run on the server.** On the server every approval would look successful with no invoice behind it, and the
image carries the fake. So:
- `docker-compose.prod.yml` hard-codes `DAFTRA_FAKE: "false"` rather than reading it from `.env`, and `env.j2` does not
  mention it;
- with the fake on and a version other than `dev`, the portal refuses to start, and `portal-deploy` goes back to the
  previous version as it does for any failed start;
- while it is on, the backend logs a warning and every page shows a strip, «دفترة تجريبية: لا يصل شيء إلى دفترة»
  (`/api/auth/me` says it is on).

**What it does not prove.** A pass on the fake shows the portal sends what we expect, not that Daftra accepts it. Before
merging anything that changes what is sent to Daftra, try it once with `DAFTRA_FAKE=false` on test records. When the
live account shows a new quirk, add it to the fake, like the ones already there.

### `modules/clients` — the customers

**Daftra is the source of truth.** The portal keeps a copy so a form can find a client by phone or code at once.

The module owns `clients`, `addresses` and `client_categories`. Its `__init__` offers:
- finding a client by phone or code, and whether a request's client is new (`known_client`,
  `existing_client_id`, today in `daftra_sync/client.py`);
- adding an address, here and in Daftra;
- the categories, each with its emirate and area;
- a client's open invoices, read from Daftra, each labelled for the drop-down;
- creating the client in Daftra when an approved request needs one, and setting its category (today in
  `daftra_sync/client.py`);
- reading a Google Maps link (today's `location.py`);
- the sync from Daftra, run by the nightly job and by the admin page.

**One fix here, a behaviour change (phase 5).** The nightly sync deletes every client and address and builds them
again from Daftra (`import_clients.replace_clients`). An address saved in the portal while Daftra refused it
(`lookups.add_client_address` keeps it and says so) is lost that night. The sync becomes an update keyed on the
Daftra id: it keeps an address Daftra has not taken, marked as such, and sends it again at the start of the next
sync. Client and address ids also stop changing every night. Check how `client_rows` reads Daftra's addresses
before changing it.

---

## 8. Jobs

Today three mechanisms run work outside a page:
- a cron line on the server calling `docker compose exec … python -m app.import_clients`;
- a `threading.Thread` and the `sync_runs` table behind the «المزامنة مع دفترة» page;
- a thread at startup warming Daftra's lists.

On top of those there are ten command-line scripts sitting next to the routers in `app/`.

After:

```
app/jobs/
├── __main__.py              python -m app.jobs <name> [options]   ·   python -m app.jobs --list
├── registry.py              @job("sync_clients", label="العملاء")
├── runner.py                runs a job and records it in job_runs (queued → running → done | failed, summary,
│                            error): in this process for cron and the command line, in a thread for the admin
│                            page; closes runs a restart left "running" (today's _busy)
├── models.py                JobRun (today's SyncRun, for any job)
├── router.py                the «المزامنة مع دفترة» page's API (today in daftra_refresh.py)
├── sync_clients.py          nightly at 23:55, and from the admin page    (today: import_clients)
├── sync_products.py         from the admin page                          (today: daftra_refresh.sync_products)
├── import_catalog.py        (today: import_packages_from_proposals)
├── import_maintenance_items.py · import_client_categories.py · import_product_images.py
├── redraw_work_orders.py · create_user.py
├── fake_daftra.py           the fake's commands: calls, fail-once, seed, reset (§7)
├── warm_daftra_cache.py     started in a thread at startup, not recorded (today: main.warm_daftra_lists)
└── legacy/                  import_final_catalog.py, import_products.py, import_daftra_priced.py — kept for
                             reference; the README says they no longer feed the catalog
```

- **A job holds no business logic.** It calls a module's service (`clients.sync_from_daftra`,
  `catalog.sync_from_daftra`, …), so the page, the cron and the command line all run the same code.
- **Cron stays.** No Redis or Celery on an 8 GB server.
- **The old command names keep working until the server is updated.** `app/import_clients.py` and the other
  scripts `deploy/ansible/import.yml` calls stay as two-line aliases. Then the cron line (`roles/sync`) and
  `import.yml` move to `python -m app.jobs …`, `ansible-playbook site.yml --tags sync` applies the cron, and the
  aliases go.

---

## 9. Frontend

### Structure

```
frontend/src/
├── main.jsx
├── app/             App.jsx (shell and menus) · routes.jsx (path → screen; old paths redirect) · nav.js (icons)
├── api/             the frontend's client of the backend: one file per backend module
│   ├── http.js      fetch, token, ApiError (today's api.js)
│   └── identity.js · requests.js · review.js · forms.js · clients.js · catalog.js · lookups.js · audit.js ·
│       notifications.js · jobs.js
├── modules/
│   ├── identity/    Login, SetPassword, Account, Users, Roles (both tabs)
│   ├── requests/    FormsCatalog, RequestForm and form/ (fields, ClientLookup, OrderLines, FormProgress),
│   │                MyRequests, RequestList, RequestView, Review, attachments, validation.js,
│   │                useFormData (today's salesData.js)
│   ├── catalog/ · lookups/ (OrderSources) · audit/ (AuditLog) · notifications/ (MailTest) · system/ (Version, Sync)
├── ds/              the design system, unchanged
└── lib/             format.js (the date and amount helpers from formsMeta.js), hooks.js, brand.js
```

- **`formsMeta.js` goes.** Each form's icon and description come with it from the API, so a new form needs no
  frontend change.
- **There is no folder per form here.** The engine draws every form from its definition. If a future form needs a
  field the engine lacks, it is added to the engine as a new field type, which every form can then use.
- **Screens call functions**, e.g. `requests.submit(id, data)` from `api/requests.js`, not `api('/requests/…')` with
  the path written in place.

### A URL for every form and request

| Path | Opens |
|---|---|
| `/forms` | النماذج: the forms this user may fill |
| `/forms/<key>` | a new request of that form (no access: the no-access page) |
| `/requests/mine` | طلباتي (tabs as `?tab=`) |
| `/requests/<id>` | one request (its owner, or view or review on its form) |
| `/requests/<id>/edit` | correcting a draft or a returned request (its owner, with submit) |
| `/review` · `/review/<id>` | المراجعة, and one request in it |
| `/admin/users` · `/admin/roles` · `/admin/audit` · `/admin/catalog` · `/admin/sync` · `/admin/order-sources` · `/admin/mail` | the admin pages |

- Bookmarkable, the back button works, and a refresh keeps the user where they were. Today the chosen form lives
  only in the page's memory.
- The approved and returned emails link straight to `/requests/<id>`.
- The old paths redirect for good, since emails already sent link to them: `/sales/new_request` → `/forms`,
  `/sales/my_requests` → `/requests/mine`, `/sales/review` → `/review`, `/admin/permissions` → `/admin/roles`,
  `/admin/daftra_sync` → `/admin/sync`, `/admin/order_sources` → `/admin/order-sources`.
- The menu still comes from `/api/auth/me`, each entry now with its path.

---

## 10. Daftra documents table

Today a request holds what approving created in seven columns: `daftra_client_id`, `daftra_invoice_id`,
`daftra_invoice_no`, `daftra_payment_id`, `daftra_receipt_no`, `daftra_work_order_id` and `daftra_work_order_no`.
A form that creates something else (a credit note for a return, an estimate for a quotation) would need more
columns.

After: `request_documents`, owned by `requests`, one row per document:

| Column | |
|---|---|
| `request_id` | the request (deleted with it) |
| `kind` | `client`, `invoice`, `payment`, `work_order` — later `credit_note`, `estimate`, … |
| `external_id` | Daftra's id |
| `number` | the number people read: invoice 06273, the receipt's, the work order's |
| `created_at` | |

- One of each kind per request, as today.
- `daftra_error` and `daftra_synced_at` stay on the request: they are about the approval, not about one document.
- Invoicing saves and finds documents through the `requests` module's `__init__`. The retry logic is unchanged:
  the invoice is found again by its `po_number`, the payment by its notes.
- The API still answers `daftra_invoice_no`, `daftra_receipt_no` and `daftra_work_order_no`, now read from the
  table, so the screens do not change.

---

## 11. Phases

**Every phase:**
- `sh backend/run-tests.sh`, `sh frontend/check.sh` and `sh frontend/ui-check/run.sh` all pass (rebuild first:
  `docker compose up -d --build backend frontend`);
- the API's paths and answers stay the same unless the phase says otherwise;
- the README sections it touches are updated in the same phase;
- it merges to `main` on its own, and after the deploy the live version is checked as in the deploy notes.

**Migrations expand, then contract.** `portal-deploy` puts the old code back if the new version does not answer,
but it cannot put the database back. So a release never removes or renames anything the release before it reads.
It adds the new thing and copies into it; the next release, once the first is confirmed live, removes the old one.
This applies to phases 5, 7 and 9.

### Phase 0 — Groundwork (small)

- Commit the work in progress; make the branch.
- `core/errors.py` and the handler in `main.py` (nothing raises those errors yet).
- `tests/test_architecture.py`. It checks whatever exists under `core/`, `integrations/`, `modules/`, `forms/` and
  `jobs/`. Files still at the root of `app/` are not checked until phase 4 moves them.

**Done when:** the tests pass and nothing else changed.

### Phase 1 — `core/` (small)

- `config.py`, `database.py` and `text.py` move to `core/`; `core/context.py` (`Actor`) and an empty
  `core/permissions.py` are added.
- `security.py` stays where it is until phase 4 splits it between `core` and `identity`. Moving it now would make
  `core` import the user model.

**Watch out:** pyflakes finds the imports left behind.
**Done when:** those files exist only in `core/`.

### Phase 2 — The Daftra client (medium)

- `daftra.py` becomes `integrations/daftra/{client,resources,cache}.py`. What is not about Daftra (§7) leaves it,
  into the folders of the modules that will hold it (`modules/clients/`, `modules/invoicing/`), even before the
  rest of those modules exists.
- The test fake patches the new client.

**Done when:** the payload tests pass with their assertions untouched; nothing under `integrations/` imports from
`modules/` or `forms/`.

### Phase 2b — The fake Daftra client (medium)

Right after the client split, so every later phase can be tried by hand without touching the live account.

- The HTTP code moves from `client.py` to `live.py`, and `client.py` becomes the switch. `tests/fake_daftra.py` moves
  to `fake.py`, with what §7 adds.
- `DAFTRA_FAKE` goes in `core/config.py`, `docker-compose.yml`, `.env.example` and `backend/.env.example`, and is
  hard-coded off in `docker-compose.prod.yml`. The README's "Run" section explains it.
- The commands of §7, as `python -m app.fake_daftra …` until phase 5 moves them to `app.jobs`. The warm-up in `main.py`
  runs the seed first when the fake is on.
- The refusal to start with a real version, the warning, and the strip on every page. `/api/auth/me` gains one field,
  `daftra_fake`.
- Tests: `conftest.py` turns the fake on with a new in-memory account per test, and `test_daftra_client.py` keeps
  testing the real HTTP code, now in `live.py`. New tests:
  - the switch picks each side;
  - the data survives a new instance read from the file;
  - seeding, then a client sync, leaves the local clients as they were;
  - the portal refuses to start with the fake on and a real version;
  - the commands refuse when it is off.

**Watch out:** the test account keeps today's ids (from 7000), so the payload tests pass untouched. Don't change what
the fake answers to suit a test.
**Done when:** on the local stack with no Daftra key, a new sale with a work order can be submitted and approved and
its PDFs opened; after `fail-once`, approving again carries on from the failed step; and `DAFTRA_FAKE=false` reaches
the live account as before.

### Phase 3 — The form engine and the 19 form folders (medium)

- Today's `app/forms/` package (`fields.py`, `options.py`, `validation.py`, `inscriptions.py`) moves to
  `modules/form_engine/`, with `FormSpec` and the registry. The name `app/forms/` is then reused for the form
  folders.
- One folder per form, all 19 (§5). The five `sync_…` functions become `on_approve` hooks, balance_payment's check
  becomes its `validate`, and the icons and descriptions come over from `formsMeta.js` (the frontend keeps its
  copy until phase 6).
- Approving calls the form's `on_approve`; submitting calls its `validate`. `daftra_sync.SYNCS` and `FORM_TYPES` go.
- Tests: every registered form has a unique key from the list of 19, a label, an icon and sections; exactly the
  five forms above have `on_approve`.

**Watch out:** a form's key is stored on its requests, so never rename one. Keep today's order of the forms (the
order of النماذج).
**Done when:** no file outside `app/forms/` names a form.

### Phase 4 — The modules (large; in steps, each green before the next)

1. `audit`, `notifications` — they depend on nothing else.
2. `identity` — `auth.py`, `account.py`, `mfa.py`, the users and roles half of `admin.py`, password links.
   `security.py` splits: token, hashing, `current_user` and `require_page` to `core/security.py`; the user loader
   registered by `identity`.
3. `catalog` — `catalog.py`, the products and picker routes of `lookups.py`, the product refresh of
   `daftra_refresh.py` (as a service).
4. `clients` — the client routes of `lookups.py`, `location.py`, the client parts of `daftra_sync/client.py` and
   `daftra.py`, the client categories, the rebuild of `import_clients.py` (as a service).
5. `lookups` — the Daftra-list routes of `lookups.py`, and `order_sources.py`.
6. `requests` — `requests_api.py`, `review.py`, and `request_label` from `audit.py`.
7. `invoicing` — the rest of `daftra_sync/`, `printouts.py`, `templates/pdf/`.
8. `system` — the version route.

Along the way:
- `models.py` is split into the modules' `models.py` files. `modules/models.py` imports them all, and
  `alembic/env.py` and `jobs/__main__.py` import it. Relationships name their class as a string (`"User"`), so no
  module imports another's models.
- The tests move to mirror the code: `tests/modules/<module>/` and `tests/forms/<key>/` (each form's Daftra
  payload tests go with it).
- No API path or answer changes, so the frontend is untouched.

**Watch out:** circular imports while splitting (User ↔ Request); the architecture test finds them early.
**Done when:** `app/` holds only `main.py`, `__init__.py`, the folders of §3 and the old command aliases, and the
architecture test checks everything.

### Phase 5 — Jobs (medium; migration; one behaviour change)

- `app/jobs/` as in §8. Every command-line script moves in, and the admin page and the nightly cron both go
  through the runner.
- The client sync updates instead of rebuilding (§7). Addresses get a column saying whether Daftra has them.
- Migration (expand): `job_runs`, with the history of `sync_runs` copied in, and the new address column.
  (Contract, next release: drop `sync_runs`.)
- `deploy/ansible/roles/sync` and `import.yml` change to `python -m app.jobs …`; run
  `ansible-playbook site.yml --tags sync`, then delete the aliases.
- The README's command lines change with it.

**Done when:** `python -m app.jobs --list` lists every job; the nightly run and a run from the page both show in
`job_runs`; `/var/log/portal-client-sync.log` still shows the nightly run; an address Daftra refused survives the
night.

### Phase 6 — Frontend structure (medium)

- The moves of §9 and the `api/` files; `formsMeta.js` goes (icons and descriptions come from the API).
- Paths and screens stay as they are; only files move.

**Done when:** `check.sh` and `ui-check` pass, and nothing imports `formsMeta.js`.

### Phase 7 — Per-form access (large; changes behaviour; migration)

- The permission registry: each form's three keys and each admin page's key. `require("…")` replaces
  `require_page`, `sales_user` and `require_admin` on every route.
- The forms list, access to each request, the review queue and the decisions are all checked per form (§6).
- `/api/auth/me` returns the user's permissions and the menu with paths. `/api/form-types` says what the user may
  do with each form. `/api/admin/pages` and `/api/admin/departments` give way to `/api/admin/permissions`.
- The roles screen gets its two tabs. «يدير الأقسام» leaves the users screen and `Account.jsx`. The menu group
  becomes «الطلبات».
- Migration (expand): `roles.permissions`, filled from `roles.pages`, and the review role for today's managers
  (§6). (Contract, next release: drop `roles.pages` and `users.manages`.)
- Tests, one per rule:
  - a technician holding only tech_extra_works sees only that form, and cannot open new_sale by URL or by API;
  - a reviewer of tech_extra_works does not see new_sale's requests;
  - view without review cannot decide;
  - a new form is closed until granted;
  - an owner still reads their request after losing submit;
  - no one but an admin decides on their own request.

  And a test of the migration itself: fixture users have exactly today's access after it.

**Watch out:** the migration must not lock anyone out. Try it on a copy of the live database and compare every
user's pages before and after.
**Done when:** every rule has a test, and on the live portal every user sees what they saw the day before.

### Phase 8 — A URL for every form and request (medium; changes behaviour)

- The routes of §9; the old paths redirect; the emails link to `/requests/<id>`.
- `ui-check/smoke.mjs` follows the new paths, and checks the redirects and that a form the user may not fill shows
  the no-access page.

**Done when:** every path in §9 opens from a fresh tab, and the old ones redirect.

### Phase 9 — Daftra documents table (medium; migration)

- Release 1 (expand): create `request_documents` and copy the seven columns into it; invoicing writes both and
  reads the table; the API answers as before.
- Release 2 (contract), once release 1 is confirmed live: stop writing the columns and drop them.

**Watch out:** approving again after a failure must still carry on from the step that failed; the retry tests
prove it.
**Done when:** the seven columns are gone, and a new kind of document needs no migration.

**Then:** the `enhancementv2.md` items, on the new structure.

---

## 12. Risks

| Risk | Guard |
|---|---|
| The deploy rolls the code back after a migration has run | Migrations expand, then contract (§11) |
| Someone loses access the day permissions change | The migration copies today's access exactly; tested on fixture users and on a copy of the live data |
| Daftra receives something different after a move | The payload tests keep their assertions through phases 1–6 |
| A form key gets renamed | The registry test pins the 19 keys |
| The server's cron and import commands call old module names | Aliases until ansible is updated (phase 5) |
| Circular imports when `models.py` is split | Relationships by class name; the architecture test |
| Old activity-log entries refer to old page keys and actions | Their labels stay |
| A long-lived branch drifts from fixes on `main` | Each phase merges as soon as it is green |
| The fake gets switched on on the server, so approvals create nothing in Daftra | Hard-coded off in the production compose file; the portal refuses to start with it on and a real version; a strip on every page |
| Something works on the fake and Daftra refuses it | One check on live test records before merging anything that changes what is sent |

---

## 13. Done when

- `app/` holds only `main.py` and the folders of §3.
- The architecture test passes, and runs in CI.
- Every form is a folder under `app/forms/`, and no file outside it names a form.
- Every form has its own fill, view and review access, set in the roles screen; a new form is closed until
  granted.
- `app/jobs/` runs every job, and every run is recorded.
- With `DAFTRA_FAKE=true` and no Daftra key, the whole flow of every invoiced form works locally, and the server cannot
  run with it on.
- The README's "Code layout", "Forms" and "Users, roles and pages" sections, and its command lines, describe the
  new structure.

---

## 14. Adding a form afterwards

1. Make `app/forms/<key>/` with `__init__.py` (the `FormSpec`) and `definition.py`, and add it to
   `app/forms/__init__.py`.
2. If approving it creates something in Daftra: `on_approve` in `hooks.py`, built from invoicing's building
   blocks, and tests in `tests/forms/<key>/` pinning what Daftra receives. A Daftra call the fake does not know yet
   gets a route in `integrations/daftra/fake.py`.
3. If it needs checks the field rules cannot express: `validate` in `hooks.py`.
4. Deploy. The form is closed to everyone but admins until, in الإدارة ← الأدوار والصلاحيات ← النماذج, roles
   are given fill, view and review.

No router, table, migration or frontend change.

---

## Appendix A: where every file goes

### Backend (`backend/app/`)

| Today | After |
|---|---|
| `main.py` | `main.py`, slimmer: mounts the routers, maps the errors, starts the warm-up |
| `config.py`, `database.py`, `text.py` | `core/` |
| `security.py` | `core/security.py` (token, hashing, current user, `require`); password links → `identity` |
| `pages.py` | `core/permissions.py` (the registry); each module declares its own pages and permissions |
| `models.py` | each module's `models.py`; `modules/models.py` imports them all |
| `auth.py`, `account.py`, `mfa.py` | `modules/identity/` |
| `admin.py` | users and roles → `identity`; the activity log page → `audit`; mail test → `notifications`; version → `system` |
| `audit.py` | `modules/audit/` (`request_label` → `requests`; the user snapshot → `identity`) |
| `mail.py`, `templates/email/` | `modules/notifications/` |
| `catalog.py` | `modules/catalog/` |
| `lookups.py` | client search, addresses, a client's details from Daftra → `clients`; products and picker → `catalog`; Daftra's lists → `lookups` |
| `order_sources.py` | `modules/lookups/` |
| `location.py` | `modules/clients/` |
| `requests_api.py`, `review.py` | `modules/requests/` (balance_payment's check → `forms/balance_payment/hooks.py`) |
| `forms/definitions.py` | `forms/<key>/definition.py`, 19 folders |
| `forms/fields.py`, `options.py`, `validation.py`, `inscriptions.py` | `modules/form_engine/` (choices only one form uses → its folder) |
| `daftra.py` | `integrations/daftra/` (addresses, cities, category locations, open invoices and their labels → `clients`; payment method keys → `invoicing`) |
| `daftra_sync/__init__.py` | the five `sync_…` → `forms/<key>/hooks.py`; `sync` → `requests` (approving) |
| `daftra_sync/client.py` | `modules/clients/` |
| `daftra_sync/invoice.py`, `common.py`, `work_order.py` | `modules/invoicing/` (new_sale's work-order fields → `forms/new_sale/`) |
| `printouts.py`, `templates/pdf/` | `modules/invoicing/` |
| `daftra_refresh.py` | `jobs/router.py`, `jobs/runner.py`, `jobs/sync_products.py` (the refresh itself → `catalog`) |
| `import_clients.py` | `jobs/sync_clients.py` (the sync itself → `clients`) |
| `import_packages_from_proposals.py` | `jobs/import_catalog.py` |
| `import_maintenance_items.py`, `import_client_categories.py`, `import_product_images.py`, `redraw_work_orders.py`, `create_user.py` | `jobs/`, same names |
| `import_final_catalog.py`, `import_products.py`, `import_daftra_priced.py` | `jobs/legacy/` |
| `tests/` | `tests/modules/<module>/`, `tests/forms/<key>/`, `tests/test_architecture.py`; `fake_daftra.py` → `integrations/daftra/fake.py` |

### Frontend (`frontend/src/`)

| Today | After |
|---|---|
| `api.js` | `api/http.js`, plus `api/<module>.js` |
| `App.jsx`, `pages.jsx`, `paths.js` | `app/` (`pages.jsx` → `routes.jsx` and `nav.js`) |
| `Login.jsx`, `SetPassword.jsx`, `Account.jsx`, `admin/Users.jsx`, `admin/Permissions.jsx` | `modules/identity/` (`Permissions` → `Roles`, with the forms tab) |
| `Sales.jsx`, `RequestForm.jsx`, `form/*`, `MyRequests.jsx`, `RequestList.jsx`, `RequestView.jsx`, `Review.jsx`, `attachments.jsx`, `validation.js`, `salesData.js` | `modules/requests/` (`Sales.jsx` → `FormsCatalog.jsx`; `salesData.js` → `useFormData.js`) |
| `admin/Catalog.jsx` | `modules/catalog/` |
| `admin/OrderSources.jsx` | `modules/lookups/` |
| `admin/AuditLog.jsx` | `modules/audit/` |
| `admin/MailTest.jsx` | `modules/notifications/` |
| `admin/DaftraSync.jsx`, `admin/Version.jsx` | `modules/system/` (`DaftraSync` → `Sync`) |
| `formsMeta.js` | removed; its date and amount helpers → `lib/format.js` |
| `hooks.js`, `brand.js` | `lib/` |
| `ds/` | unchanged |
| `tests/`, `ui-check/smoke.mjs` | follow the moves; the smoke test follows the new paths in phase 8 |

---

## Appendix B: what the final code looks like

After all the phases. The code is today's logic in its new place, trimmed. New helper names (`acting`, `holds`,
`save_document`, …) are proposals. Every package also has an `__init__.py`; the trees list it only where it
matters.

### Backend, file by file

```
backend/
├── alembic/
│   ├── env.py                     # imports app.modules.models, so it sees every table
│   └── versions/                  # one history for the whole app, as today
├── app/
│   ├── main.py                    # mounts the routers, maps errors, starts the cache warm-up
│   ├── core/
│   │   ├── config.py · database.py · text.py
│   │   ├── security.py            # token, hashing, current_user, require("form.*")
│   │   ├── permissions.py         # registry: declare(key, label, group)
│   │   ├── errors.py              # NotFound, Forbidden, Conflict, Invalid, ExternalFailure
│   │   └── context.py             # Actor (user, ip, user agent)
│   ├── integrations/
│   │   └── daftra/                # the Daftra client
│   │       ├── client.py          # the one switch: live or fake (DAFTRA_FAKE)
│   │       ├── live.py            # HTTP: calls, retries, errors, file upload, invoice PDF
│   │       ├── fake.py            # the stand-in: the same three calls, no network
│   │       ├── resources.py       # one function per Daftra call
│   │       └── cache.py           # the cached lists
│   ├── modules/
│   │   ├── models.py              # imports every module's models
│   │   ├── identity/
│   │   │   ├── __init__.py · models.py · schemas.py · repo.py
│   │   │   ├── service/           # auth · mfa · passwords · account · users · roles
│   │   │   └── router/            # auth · account · users · roles
│   │   ├── requests/
│   │   │   ├── __init__.py · models.py · schemas.py · repo.py
│   │   │   ├── service/           # access · drafts · attachments · review · documents
│   │   │   └── router/            # requests · attachments · review
│   │   ├── form_engine/           # __init__ · spec · registry · fields · options · validation · inscriptions · labels
│   │   ├── invoicing/             # __init__ · common · payment_methods · invoice · work_order · printouts · templates/pdf/
│   │   ├── clients/               # the customers: "the client for the portal"
│   │   │   ├── __init__.py · models.py · schemas.py · repo.py · service.py · router.py
│   │   │   ├── in_daftra.py       # the customer in Daftra: create, update, addresses
│   │   │   └── location.py        # Google Maps links
│   │   ├── catalog/               # __init__ · models · schemas · repo · service · router
│   │   ├── lookups/               # __init__ · schemas · service · router
│   │   ├── audit/                 # __init__ · models · schemas · repo · service · labels · router
│   │   ├── notifications/         # __init__ · schemas · service · router · templates/email/
│   │   └── system/                # __init__ · router
│   ├── forms/                     # listed in today's order, which is the order of النماذج
│   │   ├── __init__.py            # imports all 19, which registers them
│   │   ├── new_sale/              # __init__ · definition · hooks · work_order (its Daftra fields)
│   │   ├── contract_renewal/      # __init__ · definition · hooks
│   │   ├── maintenance/           # __init__ · definition · hooks
│   │   ├── balance_payment/       # __init__ · definition · hooks
│   │   ├── quotation/             # __init__ · definition (same for the 13 below)
│   │   ├── quote_to_invoice/ · order_addition/ · order_modification/ · return_refund/
│   │   ├── tech_cash_collection/ · reinstallation/ · data_entry_error/ · pre_sale_inspection/
│   │   ├── installation_completed/ · contract_service_done/ · open_ticket/ · close_ticket/ · daily_visits/
│   │   └── tech_extra_works/      # __init__ · definition · hooks
│   └── jobs/
│       ├── __main__.py            # python -m app.jobs <name> | --list
│       ├── registry.py · runner.py · models.py (JobRun) · router.py (the sync page)
│       ├── sync_clients.py · sync_products.py · import_catalog.py · warm_daftra_cache.py
│       ├── import_maintenance_items.py · import_client_categories.py · import_product_images.py
│       ├── redraw_work_orders.py · create_user.py · fake_daftra.py
│       └── legacy/                # the three old catalog imports
└── tests/
    ├── conftest.py · seed.py · test_architecture.py
    ├── integrations/ · jobs/
    ├── modules/<module>/test_*.py
    └── forms/<key>/test_*.py      # each form's Daftra payload tests
```

### Frontend, file by file

```
frontend/src/
├── main.jsx · styles.css
├── app/          App.jsx · routes.jsx · nav.js
├── api/          http.js · identity.js · requests.js · review.js · forms.js · clients.js
│                 catalog.js · lookups.js · audit.js · notifications.js · jobs.js
├── modules/
│   ├── identity/       Login · SetPassword · Account · Users · Roles · RoleEditor · FormAccess
│   ├── requests/       FormsCatalog · NewRequest · RequestForm · MyRequests · RequestList
│   │   │               RequestView · Review · attachments · validation.js · useFormData.js
│   │   └── form/       fields · ClientLookup · OrderLines · FormProgress
│   ├── catalog/        Catalog
│   ├── lookups/        OrderSources
│   ├── audit/          AuditLog
│   ├── notifications/  MailTest
│   └── system/         Sync · Version
├── ds/           unchanged
└── lib/          format.js · hooks.js · brand.js
```

### One module: `modules/clients/`

**`__init__.py`: the only thing other modules may import**

```python
"""The portal's customers. Daftra stays the source of truth; this is our copy, for finding a client at once."""

from .in_daftra import create_in_daftra, held_custom_fields, update_in_daftra
from .router import router
from .service import add_address, categories, existing_client_id, known_client, lookup, open_invoices, sync_from_daftra
```

**`models.py`: this module's tables**

```python
class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    daftra_id: Mapped[int] = mapped_column(unique=True)
    client_code: Mapped[str] = mapped_column(String(10), unique=True)
    phone: Mapped[str] = mapped_column(String(20), index=True, default="", server_default="")
    # … the other columns as today
    addresses: Mapped[list["Address"]] = relationship(back_populates="client", cascade="all, delete-orphan")


class Address(Base):
    __tablename__ = "addresses"
    # … as today, plus:
    in_daftra: Mapped[bool] = mapped_column(default=True, server_default="true")  # False: the sync keeps it and resends it
```

**`schemas.py`: what comes in and goes out**

```python
class AddressIn(BaseModel):
    emirate: str = Field("", max_length=50)
    area: str = Field("", max_length=100)
    street: str = Field("", max_length=200)
    house: str = Field("", max_length=100)
    location_url: str = Field("", max_length=600)
    coordinates: str = Field("", max_length=100)

# AddressOut and ClientMatch: the same answers as today's address_out and client_match
```

**`repo.py`: queries only, never commits**

```python
def by_code(db: Session, code: str) -> Client | None:
    return db.scalar(select(Client).where(Client.client_code == code).options(selectinload(Client.addresses)))


def by_phone(db: Session, phone: str) -> list[Client]:
    return db.scalars(select(Client).where(or_(Client.phone == phone, Client.phone2 == phone))
                      .options(selectinload(Client.addresses))).all()


def by_daftra_id(db: Session, daftra_id: int) -> Client | None:
    return db.scalar(select(Client).where(Client.daftra_id == daftra_id))
```

**`service.py`: the business rules, with no HTTP**

```python
def lookup(db: Session, phone: str = "", code: str = "") -> list[Client]:
    if phone:
        wanted = local_phone(phone)
        return repo.by_phone(db, wanted) if len(wanted) >= 9 else []
    wanted = digits(code).zfill(6)
    found = repo.by_code(db, wanted) if wanted.strip("0") else None
    return [found] if found else []


def add_address(db: Session, who: Actor, daftra_id: int, fields: dict) -> tuple[Address, str]:
    """Saves the address here, then in Daftra. Returns it, and why Daftra refused it if it did."""
    client = repo.by_daftra_id(db, daftra_id)
    if client is None:
        raise NotFound("العميل غير موجود")           # the handler in main.py turns this into a 404
    address = Address(client=client, in_daftra=False, emirate=fields["emirate"], area=fields["area"],
                      street=fields["street"], house=fields["house"], link=fields["location_url"])
    db.add(address)
    db.flush()
    audit.log(db, who, "client.address.add", "client", client.id, client.customer_name, after=fields)
    db.commit()
    try:
        in_daftra.save_address(daftra_id, fields)
    except (Conflict, daftra.DaftraError) as error:
        return address, str(error)
    address.in_daftra = True
    db.commit()
    return address, ""

# existing_client_id, known_client, open_invoices, categories, sync_from_daftra: today's code, moved (§7)
```

**`router.py`: the transport, with the same paths as today**

```python
router = APIRouter(prefix="/api")
form_user = require("form.*")     # anyone with a permission on any form


@router.get("/clients/lookup")
def lookup_client(phone: str = "", code: str = "", user=Depends(form_user), db: Session = Depends(get_db)):
    return {"matches": [schemas.ClientMatch.of(client) for client in service.lookup(db, phone, code)]}


@router.post("/clients/{daftra_id}/addresses")
def add_client_address(daftra_id: int, body: schemas.AddressIn, who: Actor = Depends(acting(form_user)),
                       db: Session = Depends(get_db)):
    address, problem = service.add_address(db, who, daftra_id, body.model_dump())
    return {**schemas.AddressOut.of(address).model_dump(), "saved_in_daftra": not problem, "daftra_error": problem}
```

### One form: `forms/balance_payment/`

**`__init__.py`**

```python
from app.modules.form_engine import FormSpec, register

from . import definition, hooks

register(FormSpec(
    key="balance_payment",        # stored on every request: never rename
    label="طلب تسديد مبلغ متبقي",
    icon="send",
    description="سداد المبلغ المتبقي على طلب",
    sections=definition.SECTIONS,
    daftra_note="ويُنشأ في دفترة سند قبض بالمبلغ المدفوع على الفاتورة المختارة.",
    validate=hooks.validate,
    on_approve=hooks.on_approve,
))
```

**`definition.py`: moved as it is from today's `definitions.py`**

```python
SECTIONS = [
    request_info("تاريخ الطلب", source=False),
    section(
        "بيانات العميل",
        f("phone", "رقم الهاتف", "phone", True),
        f("client_code", "كود العميل", required=True, pattern=r"^\d{1,6}$", pattern_message="أرقام فقط، حتى 6 خانات"),
        f("customer_name", "اسم العميل", required=True, max_length=150),
        f("invoice", "رقم الفاتورة", "daftra_client_invoice", True),
    ),
    section("قيمة الطلب", money("paid_amount", "المبلغ المدفوع الآن", True, positive=True)),
    # … تفاصيل الدفعة, attachments and NOTES, as today
]
```

**`hooks.py`: only what makes this form different**

```python
def validate(data: dict, ctx: CheckContext) -> dict:
    """Today this check is hard-coded in the shared requests_api.apply_action."""
    invoices = ctx.choices.get("daftra_client_invoice") or []
    chosen = next((i for i in invoices if i["id"] == data.get("invoice")), None)
    if chosen and data.get("paid_amount", 0) > chosen["unpaid"] + 0.005:
        return {"paid_amount": f"المبلغ أكبر من المتبقي على الفاتورة ({chosen['unpaid']:,.2f} درهم)"}
    return {}


@invoicing.reports_daftra_errors
def on_approve(ctx: ApprovalContext) -> dict:
    """A receipt on the chosen invoice (today's sync_balance_payment)."""
    request, data = ctx.request, ctx.request.data
    paid, method = invoicing.payment_inputs(data)
    try:
        invoice = invoicing.get_invoice(int(data["invoice"]))
    except daftra.NotFound:
        raise Conflict(f"الفاتورة {data.get('invoice_name') or data['invoice']} لم تعد موجودة في دفترة. "
                       "أعد الطلب للموظف ليختار الفاتورة الصحيحة.")
    requests.save_document(ctx.db, request, "client", int(invoice["client_id"]))
    requests.save_document(ctx.db, request, "invoice", int(invoice["id"]), invoice.get("no"))
    # … the check that paid is not more than unpaid, as today
    return invoicing.finish(request, invoice, paid, method, ctx.reviewer, ctx.db)
```

A form with no Daftra side effects, like `quotation/`, has only `__init__.py` and `definition.py`.

### Where the engine meets a form

**`modules/form_engine/spec.py`: the contract every form fills in**

```python
@dataclass(frozen=True)
class FormSpec:
    key: str
    label: str
    icon: str
    description: str
    sections: list[dict]
    visible: bool = True                 # False: no new requests; old ones can still be reviewed
    daftra_note: str = ""
    validate: Callable | None = None     # (data, ctx) -> {field: message}
    on_approve: Callable | None = None   # (ctx) -> summary for the activity log

    @property
    def invoiced(self) -> bool:          # RequestView.jsx reads this
        return self.on_approve is not None


# Any: form_engine knows nothing about the requests or identity modules
@dataclass
class CheckContext:
    db: Session
    user: Any
    choices: dict        # what the form's list fields offered, by field type; one that could not be loaded is left out


@dataclass
class ApprovalContext:
    request: Any         # what is created is kept on it, step by step
    db: Session
    reviewer: Any        # the approving user, the receipt's المستلم
```

**`modules/requests/service/access.py`: access per form**

```python
def can_view(request: Request, user) -> bool:
    """Its owner always; anyone else needs view or review on this request's form."""
    form = request.form_type
    return request.created_by_id == user.id or holds(user, f"form.{form}.view", f"form.{form}.review")
```

**`modules/requests/service/review.py`: never names a form**

```python
def approve(db: Session, who: Actor, request_id: int, revision: int) -> Request:
    request = repo.lock(db, request_id)                     # two managers cannot both approve
    access.check_can_decide(request, who.user, revision)    # form.<key>.review, same revision, not their own
    spec = form_engine.get(request.form_type)
    summary = {}
    if spec.on_approve:
        try:
            summary = spec.on_approve(ApprovalContext(request=request, db=db, reviewer=who.user))
        except DomainError as error:
            record_failure(db, who, request, str(error))    # what was created stays; approving again carries on
            raise
        # An unexpected error is recorded the same way and answers 500, as today
    # … status, history, email to the owner and activity log, as today
    db.commit()
    return request
```

### A job and the frontend client

```python
# app/jobs/sync_clients.py: the job only runs it; the rules live in the module
@job("sync_clients", label="العملاء", on_admin_page=True)
def sync_clients(db, who):
    return clients.sync_from_daftra(db, who)
```

```js
// frontend/src/api/clients.js: the paths live here and nowhere else
export const lookupClient = ({ phone = '', code = '' }) => api(`/clients/lookup?${new URLSearchParams({ phone, code })}`);
export const addClientAddress = (daftraId, address) => api(`/clients/${daftraId}/addresses`, { method: 'POST', body: address });
```

### One click through every layer

A manager clicks «اعتماد» on a balance payment:

```
Review.jsx → api/review.js                     frontend
POST /api/review/requests/42/approve           HTTP
modules/requests/router/review.py              transport: reads the input
modules/requests/service/review.py             service: locks the row, checks form.balance_payment.review
forms/balance_payment/hooks.py                 the form: what this one creates
modules/invoicing/invoice.py                   the steps: payment, receipt, PDFs
integrations/daftra/resources.py → client.py   the Daftra client
  → live.py (the HTTP call) or fake.py         DAFTRA_FAKE decides
```
