# FutureLife Portal

Staff log in and see the departments and pages their roles allow. Sales users pick a form
type, fill the form and submit it; admins manage users, roles and the audit log.

- `backend/` — FastAPI + SQLAlchemy + PostgreSQL
- `frontend/` — React (Vite)

## Run

The whole stack — database, mail catcher, backend and frontend — runs with:

```
docker compose up --build
```

Open http://localhost:5174. First time, or to set a real Daftra key, a strong `JWT_SECRET`, or
real SMTP settings: copy `.env.example` to `.env` (same folder as `docker-compose.yml`) and set
them there; `docker compose up` picks it up automatically. The backend reloads code changes on
every request only if restarted (`docker compose restart backend`); the frontend's Vite dev
server hot-reloads on save like it does outside Docker.

### The fake Daftra account

Locally the portal does **not** talk to Daftra. A stand-in inside it answers instead, so the whole
flow can be tried by hand — fill a form, approve it, open the invoice, receipt and work order, fail
midway and approve again — without real numbered invoices on the live account. No Daftra key is
needed, and a portal on your machine cannot write to the live account by accident.

```
DAFTRA_FAKE=true     # the stand-in (the default locally)
DAFTRA_FAKE=false    # the live account, with DAFTRA_SUBDOMAIN and DAFTRA_API_KEY
```

Apply a change with `docker compose up -d backend` — `docker compose restart` keeps the old value.
While it is on, the backend logs a warning and every page shows a strip, «دفترة تجريبية: لا يصل شيء
إلى دفترة».

It is filled from the local database on every start, adding what it has not seen: clients with their
addresses, the products linked to Daftra, the categories, and the staff linked to users. Otherwise
approving for an existing client would fail, because the stand-in had never seen its Daftra id. It
keeps its data in `uploads/fake_daftra.json` (gitignored — it holds client data), so a restart does
not forget invoices that requests still point at. Its ids start at 900000001, so a fake id that ever
reached the live account would find nothing rather than a real record.

Its commands, with the stack up:

```
docker compose exec backend python -m app.jobs fake_daftra calls                                  # the last 20 calls
docker compose exec backend python -m app.jobs fake_daftra fail-once /api2/invoice_payments.json  # fail that call once
docker compose exec backend python -m app.jobs fake_daftra seed                                   # add what the database gained
docker compose exec backend python -m app.jobs fake_daftra reset                                  # forget everything
```

**It cannot run on the server.** `docker-compose.prod.yml` hard-codes it off, and the portal refuses
to start with it on and a version other than `dev`, so a mistake stops the deploy instead of losing
invoices.

**What it does not prove.** A pass on the stand-in shows the portal sends what we expect, not that
Daftra accepts it. Before merging anything that changes what is sent to Daftra, try it once with
`DAFTRA_FAKE=false` on test records. When the live account shows a new quirk, add it to
`backend/app/integrations/daftra/fake.py`, like the ones already there.

### Running without Docker

Useful for a backend you want to `--reload` on every save. Database and mail catcher still need
Docker:

```
docker compose up -d db mail
```

Backend (from `backend/`, first time only: create the venv, install, copy `.env.example` to
`.env` and set `JWT_SECRET`):

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8001
```

Frontend (from `frontend/`):

```
npm install
npm run dev
```

Open http://localhost:5174.

## Users, roles and permissions

The first admin is created from the command line (from `backend/`):

```
.venv\Scripts\python -m app.jobs create_user <username> <password> --admin --name "Full Name" --email you@example.com
```

Everything after that is done in the portal, under the الإدارة tab:

- **المستخدمون** — add users, edit them, stop an account, send a link to set a new password.
- **الأدوار والصلاحيات** — roles. A role is a set of permissions; a user holds the permissions of
  all their roles. Two tabs over the same data: **الأدوار** (one role at a time, a row per form
  with three boxes, then the admin pages) and **النماذج** (one form at a time: which roles can
  fill it, see it and review it).
- **سجل النشاط** — every login, change and file download, with the values before and after.

A new user gets an email with a link to set their own password (valid 72 hours, single use),
and then logs in with their email or username. "نسيت كلمة المرور؟" on the login screen and
"رابط كلمة المرور" in the users table send the same kind of link. If an email cannot be sent,
the admin is shown the link to pass on by hand.

### Access is per form

Every form has three permissions, made from its key — nobody writes them by hand:

| Permission | Lets the user |
|---|---|
| `form.<key>.submit` | see the form in النماذج, fill it, save drafts, submit, correct their own returned requests |
| `form.<key>.view` | see everyone's requests of this form, with their files, without changing them |
| `form.<key>.review` | see them in المراجعة and approve or return them |

Each admin page has one of its own: `admin.audit`, `admin.catalog`, `admin.sync`,
`admin.order_sources`, `admin.mail`. `admin.users` and `admin.roles` stay admin-only, because
whoever held them could give themselves anything; the rest can be put in a role, so someone can
keep the catalog without being an admin.

The rules:

- **A new form is closed.** Only admins see it until an admin grants `form.<key>.submit` to a
  role. Its three keys show up in the roles screen by themselves.
- A hidden form takes no new requests; view and review still work on its old ones.
- Nobody decides on their own request, except an admin.
- The owner can always open their own request, even after losing `submit`. They can change a
  draft only while they still hold `submit` for that form.
- The lookups the forms use (client search, products, Daftra's lists) are open to anyone holding
  any form permission.
- **The server checks every call**: opening a form, creating, saving, submitting, uploading,
  viewing, deciding. Hiding a button is never the check.

A reviewer of one form does not see another form's requests at all — not in المراجعة, not by URL,
not by API.

Every user has a حسابي page (their name in the header): name, password and two-step login.
Two-step login is a 6-digit code emailed after the password (valid 10 minutes, single use).
It is always on for admins and a choice for everyone else, so an admin must have an email
and email must be working. If it is not, `REQUIRE_ADMIN_MFA=false` in `backend/.env` lets
admins in with the password alone until it is fixed.

A user with no requests can be deleted; one with requests can only be stopped, because a request
keeps its owner. Eight failed logins on one account block it for 15 minutes.

An admin holds every permission.

The menu comes from `/api/auth/me`, each entry with its own path, and is built from the
permissions the user holds (`backend/app/core/permissions.py`, which also declares every
permission). The «المبيعات» group is **«الطلبات»**: the forms are no longer sales-only, so a
technician's النماذج would otherwise sit under المبيعات.

To protect a route, give it `require("<key>")` — or `require_any_form("submit")` for a screen
that opens when any one form does.

### A URL for every screen, form and request

| Path | Opens |
|---|---|
| `/forms` | النماذج: the forms this user may fill |
| `/forms/<key>` | a new request of that form (no access: the no-access page) |
| `/requests/mine` | طلباتي (tabs as `?tab=`) |
| `/requests/<id>` | one request (its owner, or view or review on its form) |
| `/requests/<id>/edit` | correcting a draft or a returned request |
| `/review` · `/review/<id>` | المراجعة, and one request in it |
| `/admin/users` · `/admin/roles` · `/admin/audit` · `/admin/catalog` · `/admin/sync` · `/admin/order-sources` · `/admin/mail` | the admin pages |

Bookmarkable, the back button works, and a refresh keeps the user where they were. The approved
and returned emails link straight to `/requests/<id>`. The paths the portal used before redirect
for good, because emails already sent link to them (`frontend/src/app/routes.jsx` lists both the
routes and the redirects).

## Requests and review

A request goes draft → submitted → returned (back to its owner with a reason) or approved.
A returned request is corrected by its owner and submitted again, which raises its revision;
a decision always applies to the revision the manager looked at. Sales managers (users who
manage the sales department) review under المبيعات → المراجعة; nobody but the system admin
decides on their own request. Each step is kept in the request's history, and the owner is
emailed when a request is returned or approved.

Forms are defined in `backend/app/forms/definitions.py`. The last eight (reinstallation to daily_visits)
were drafted from the design's form catalog and their fields still need the business's review.

## Products and packages

Three tables hold the catalog: `products` (a single unit with nothing inside it), `packages`
(one or more products sold together) and `product_to_package` (which products a package holds,
each with its own quantity, price and line discount). Admins manage both under
الإدارة → المنتجات والباقات. The sales forms' product field searches this catalog
(`GET /api/products`), not Daftra's live product list, which carries many duplicate names.

**The catalog is built from the Proposal quotation PDFs and Daftra's `products.json`** (both in
the workspace folder, next to `portal/`). Each PDF is the Daftra quotation of one package; its
lines give the package's products, quantities and prices, and each product is matched to Daftra's
by name to carry its Daftra id (which the invoices need). From `backend/`, read the report of a dry
run first, then run it for real:

```
.venv\Scripts\python -m app.jobs import_catalog --dry-run
.venv\Scripts\python -m app.jobs import_catalog
```

This **replaces** the whole catalog: every product, package and product-to-package link is
deleted and rebuilt, so anything added by hand in the portal since does not survive a rerun. The
maintenance items are then added on top (see طلب صيانة وتبديل below), and on the server both run
from `deploy/ansible/import.yml`.

Three older import scripts are kept for reference but are no longer the catalog's source:
`import_final_catalog.py` (the `Products.xlsx` workbook), `import_products.py` (a quotation-lines
workbook, merged in) and `import_daftra_priced.py` (Daftra products that carry a price). Running
any of them after the proposals import changes the catalog away from the quotations.

## Daftra invoices on approval

Approving one of these requests creates its documents in Daftra. What each form creates is in its
own folder (`app/forms/<key>/hooks.py`), built from the steps in `app/modules/invoicing/`; the
review code never names a form, it asks the form. The invoice PDF and the receipt PDF are attached
to the request. The receipt and work order PDFs are drawn by the portal
(`modules/invoicing/printouts.py`, templates in `modules/invoicing/templates/pdf/`), since
Daftra's API has none:

- **طلب بيع لعميل جديد**: the client when new, the invoice, and the receipt (سند قبض) for the amount paid.
  When «إنشاء أمر الشغل» is نعم, it also creates the installation work order, and attaches a PDF of it
  drawn by the portal:
  - with the approving manager written in it as «المسؤول» (Daftra records the API user as its creator);
  - assigned to the salesperson who sent the request, under «معلومات الموظفين المعينين»;
  - starting on the approval day and due after «مدة التركيب» days;
  - linked to the invoice;
  - with the custom fields of our work-order form filled from the request (ملحقات التركيب، الألوان المتاحة،
    ظهر الكفر، لون القاعدة، …). These are set by a `CustomModel` edit and read back to confirm, since Daftra
    answers it with an error page (`WORK_ORDER_FIELDS` in `daftra_sync/work_order.py`). «صورة المنتج» is required but
    the API cannot upload a file, so it gets a text placeholder; staff replace it with the photo in Daftra.
- **طلب تجديد عقد الصيانة السنوي**: for an existing client only. It sets the client's category (التصنيف),
  then creates the one-line "exchange contract" invoice and its receipt.
- **طلب تسديد مبلغ متبقي**: a receipt on the invoice picked from the client's invoices that still have money due.
- **طلب صيانة وتبديل**: the client when new, an invoice of the items picked under «إضافة بند», and a receipt
  when something was paid (it must be paid in full).
  - The invoice notes list the devices, the service and the visit date. (Requests from before «وصف الخدمة»
    was removed from the form still put it on the general «service» item.)
  - The items are the catalog products with a maintenance group, at their catalog price. Prices and groups
    are edited in الإدارة ← المنتجات والباقات. They came from `Maintenance_Invoice_Items.xlsx`:
    `.venv\Scripts\python -m app.jobs import_maintenance_items`.
- **اعمال اضافية (قسم الفنيات)**: an invoice of the works picked for a client Daftra already has, and a receipt
  when something was paid. Its four works are named by their Daftra id, and each must be in the catalog:
  - تمديد المياة 6, تمديد الكهرباء 7 and اعمال باسكو 10 are the form's own prices (`TECH_SERVICE_PRICES` in
    `app/forms/tech_extra_works/definition.py`). The server applies them over the catalog's, on this form only:
    the same products keep the catalog's price sold alone elsewhere, and their own price in a package.
  - «أخرى» is described and priced on its line.

In a form's address (`frontend/src/modules/requests/address.js`):

- picking a «التصنيف» replaces المنطقة and الإمارة with its own, a client's neighbourhood included. The
  التصنيف Daftra holds for a found client only fills them while they are empty;
- a known «المنطقة» sets its الإمارة;
- each narrows the lists after it: the الإمارة narrows the areas and the categories, the المنطقة the categories.
  A typed neighbourhood is on no list, so it narrows nothing and the emirate's categories are offered;
- what no longer belongs after a change is emptied: a التصنيف or a region of another emirate;
- changing the phone or client code a client was found by empties the whole address, and what the search
  filled in, so a new search starts clean.

The forms' «التصنيف» (Daftra's client categories, each with the المنطقة and الإمارة it fills in) is read from
our own `client_categories` table, never from Daftra on a request. The portal fills the table once, the first
time it starts with it empty. To refresh it after categories change in Daftra, run the following from
`backend/` (it reads every client, so it takes a few minutes):

```
.venv\Scripts\python -m app.jobs import_client_categories
```

Other form types are not sent to Daftra yet. Before it works for a salesperson:

- Link their portal user to their Daftra staff member (الإدارة → المستخدمون → الموظف في دفترة); it is the
  sales person on the invoice.
- Every product in the order needs its Daftra id (`daftra_id`). Saving a new product on the catalog page creates it in Daftra as an untracked service and keeps its id and code; editing one changes the portal only.

If Daftra refuses or cannot be reached, the request is not approved and the manager sees why. Approving
again continues from the step that failed. The invoice's `po_number` and the payment's notes carry
`PORTAL-<request id>`, so neither is ever created twice.

### What a request created, in Daftra

Each document lives in `request_documents`, one row per request and kind — `client`, `invoice`,
`payment`, `work_order`, and later a `credit_note` or an `estimate` without a migration. Every row
carries Daftra's own id and the number people read (invoice 06273, the receipt's, the work
order's).

Each id is kept as soon as its step succeeds, so approving again after a failure carries on from
the step that failed instead of creating anything twice. If an id was lost (the answer never
arrived), the invoice is found again by its `po_number` and the payment by its notes, both
`<DAFTRA_MARKER_PREFIX>-<request id>`. `daftra_error` and `daftra_synced_at` stay on the request
itself: they are about the approval, not about one document.

The seven `daftra_*_id` / `daftra_*_no` columns these replaced are still written, because a deploy
that rolls the code back can put the old code back but not the database. **The next release stops
writing them and drops them** — see `final_plan.md` §11 and the note in
`alembic/versions/0021_request_documents.py`.

## Email

`docker compose up -d` also starts a mail catcher: every email the portal sends in development
lands in the inbox at http://localhost:8026 instead of going out. For real email, set
`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_STARTTLS` and `MAIL_FROM` in
`backend/.env` to your provider's values, and `PUBLIC_URL` to the address users open the portal at.

Each email is a pair of Jinja2 templates in `backend/app/templates/email/`: `<name>.html` for the
designed version and `<name>.txt` for plain text. `base.html` holds the shared look (header,
colours, footer) and `_macros.html` the button and note box, so a change there reaches every
email. To add an email, add the two templates and a small `send_...` function in `backend/app/mail.py`.

## Database changes

The backend applies the migrations in `backend/alembic/versions/` on startup.
After changing `backend/app/models.py`, add a migration (from `backend/`):

```
.venv\Scripts\python -m alembic revision --autogenerate -m "what changed"
```

## Forms

Every form is a folder, `backend/app/forms/<key>/`:

- `__init__.py` — its `FormSpec`: the key (stored on every request, so **never rename one**), its
  label, icon and description, whether it is visible, and what approving it creates in Daftra.
  Importing the folder registers the form.
- `definition.py` — its sections and fields, written with the building blocks the form engine
  offers, plus the choices only this form uses.
- `hooks.py` — only where the form differs: `validate` for a check the field rules cannot express,
  `on_approve` for what approving creates outside the portal.

`backend/app/modules/form_engine/` is the engine: `spec.py` (what a form is), `registry.py` (where
the forms put themselves), `fields.py` (the building blocks), `options.py` (the choices more than
one form offers), `validation.py`, `inscriptions.py`. Everything a form needs comes from the
engine's `__init__.py`, which is the only way in.

The engine never names a form — a search for a form key outside `app/forms/` finds nothing. The
frontend renders whatever the definitions say, and `validation.py` checks a submission against
them; `frontend/src/validation.js` repeats the same checks for instant feedback.

To add a form, see "Adding a form" in `final_plan.md` §14: a folder and one line in
`app/forms/__init__.py`, with no router, table, migration or frontend change.

## Code layout

The backend is a modular monolith: one app, one database, one deploy, with the code in layers.
A file imports from its own layer or a lower one, never a higher one, and reaches another module
only through its `__init__.py`. `tests/test_architecture.py` reads every import and fails
otherwise. The move is happening in phases (`final_plan.md`), so some files are still at the root
of `app/`.

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

Backend (`backend/app/`):

- `main.py` starts the app, includes the routers and turns a service's error into its HTTP status.
- `core/` — shared by everything, with no business rules: `config.py` (settings), `database.py`
  (engine, session, migrations), `security.py` (the token, hashing, the current user, what a route
  needs), `errors.py` (what a service raises, and the status each becomes), `context.py` (`Actor`:
  who is acting and from where), `permissions.py`, `text.py` (Arabic digits, UAE time).
- `integrations/daftra/` — the Daftra client, and the only code that talks to Daftra:
  `client.py` (the one switch: live or fake), `live.py` (the HTTP calls, retries, file upload,
  invoice PDF), `fake.py` (the stand-in, see "The fake Daftra account"), `resources.py` (one
  function per call the portal makes), `cache.py` (the lists kept for a while), `errors.py`.
- `modules/` — the business areas, each owning its own tables and reached only through its
  `__init__.py`:
  - `identity/` — logging in and out, the two-step codes, the password links, the account page,
    and the users and roles screens (`service/` and `router/`, split by topic).
  - `requests/` — a request's draft, its files, its history and its review (`service/` and
    `router/`, split by topic). It never imports `invoicing`: approving asks the form.
  - `form_engine/` — what a form is and what forms are built from (see "Forms").
  - `clients/` — the portal's customers: our copy of Daftra's clients, the city table, their
    addresses here and in Daftra, the categories, a client's open invoices, map links.
  - `catalog/` — the products and the packages built from them.
  - `lookups/` — Daftra's staff, treasuries and order sources, and the «مصادر الطلب» page.
  - `invoicing/` — what approving a request creates in Daftra.
  - `audit/` — the activity log and its page. Every module writes to it, so it sits below them
    all: a module with labels or lists of its own registers them (`add_value_labels`,
    `set_user_lister`) rather than audit reaching up.
  - `notifications/` — the emails, their templates, and the page that tests them.
  - `system/` — which version is running.
  - `models.py` — imports every module's models, for SQLAlchemy and Alembic.
- `forms/` — one folder per form (see "Forms").
- Only `main.py` and the old command aliases are left at the root of `app/` (see `jobs/`).
- `jobs/` — everything the portal does outside a page: the nightly client sync, the
  «المزامنة مع دفترة» page's buttons, and the command-line imports. One runner records every run
  in `job_runs`, and a job holds no business rules of its own: it calls a module's service, so the
  page, the cron and the command line all run the same code.

```
python -m app.jobs --list                  what there is to run
python -m app.jobs sync_clients            run one (recorded in job_runs)
```

  The old command names (`python -m app.import_clients`, …) still work as thin aliases, so a
  server whose cron has not been re-provisioned keeps running. Delete `backend/app/import_*.py`,
  `create_user.py` and `fake_daftra.py` once `ansible-playbook site.yml --tags sync` and
  `import.yml` have run with the new commands.

Frontend (`frontend/src/`), laid out like the backend:

- `app/` — the shell: `App.jsx` (layout and navigation), `routes.jsx` (which screen each page key
  opens), `nav.js` (each page's path and icon).
- `api/` — the frontend's client of the backend, one file per backend module: `http.js` (fetch, the
  token, `ApiError`) and `identity.js`, `requests.js`, `review.js`, `clients.js`, `catalog.js`,
  `lookups.js`, `audit.js`, `notifications.js`, `jobs.js`, `system.js`. **Every API path lives
  here and nowhere else** — a screen calls `requests.updateRequest(id, body)`, never
  `api('/requests/…')`.
- `modules/` — the screens, by business area: `identity/` (Login, SetPassword, Account, Users,
  Roles), `requests/` (FormsCatalog, RequestForm and `form/`, MyRequests, RequestList,
  RequestView, Review, attachments, validation.js, useFormData.js), `catalog/`, `lookups/`,
  `audit/`, `notifications/`, `system/`.
- `ds/` — the design system's components, tokens, styles and search matcher.
- `lib/` — `format.js` (how dates and amounts are written), `hooks.js`, `brand.js`.

A form's icon and description come with it from the API, so adding a form needs no frontend
change at all.

## Tests

Backend tests run in Docker against a separate `portal_test` database of the local stack, with
Daftra replaced by an in-memory fake that records every call (a test cannot reach the network)
and email caught in a list. They pin, among the rest, the exact payloads sent to Daftra for each
invoiced form. With the stack up (`docker compose up -d`), from `backend/`:

```
sh run-tests.sh            # pyflakes, then every test
sh run-tests.sh -k review  # pytest arguments are passed on
```

Frontend: `sh check.sh` from `frontend/` runs the tests in `frontend/tests/` (`node --test`,
no extra packages) and a production build.

Browser check: `sh frontend/ui-check/run.sh` drives the running local stack in a headless browser
(the Playwright image) at a desktop and a phone width. Every page must render without an error,
the new-sale form must work end to end, and every field of every visible form must be on the
screen. It signs in with a token made in the backend container and blocks every call that would
change data. Screenshots land in `frontend/ui-check/shots/`.

## Deploying to AWS (EC2)

`deploy/terraform` creates the server and `deploy/ansible` installs and updates the portal on it. The
server is an m7i-flex.large with Ubuntu Pro 24.04, in me-central-1 (UAE), with a fixed public IP. The
portal answers on plain HTTP at that IP. Run everything from WSL (Ubuntu), which needs:
`sudo apt install ansible unzip`, [Terraform](https://developer.hashicorp.com/terraform/install), the
AWS CLI (`aws configure` with a key allowed to manage EC2), and an SSH key (`ssh-keygen -t ed25519`
if `~/.ssh/id_ed25519` doesn't exist).

What runs on the server is `docker-compose.prod.yml`: Postgres, the backend, and Caddy. Caddy serves
the built React app and passes `/api` on to the backend. Only ports 22 (from your IP) and 80 are open.

**1. Create the server.** Do this once.

```sh
cd "/mnt/d/Hopa Work/Automation/portal/deploy/terraform"
cp terraform.tfvars.example terraform.tfvars   # set ssh_allowed_cidrs to your IP/32
terraform init
terraform apply                                # prints public_ip and portal_url
```

This also writes `deploy/ansible/inventory.ini` with the server's IP. Keep `terraform.tfstate` safe: it
is not committed, and Terraform needs it to change or destroy the server later.

- **"No Ubuntu Pro image found":** subscribe to "Ubuntu Pro 24.04 LTS" in the AWS Marketplace. Put its
  AMI id in `ami_id`.
- **"m7i-flex.large is not supported":** that instance type isn't offered in your account or zone.
  Set `instance_type`, e.g. `m7i.large`.

**2. Settings and secrets.** Do this once.

```sh
cd ../ansible
cp group_vars/all/vault.yml.example group_vars/all/vault.yml
nano group_vars/all/vault.yml        # Daftra and SMTP values from the workspace .env; two new random secrets
ansible-vault encrypt group_vars/all/vault.yml
```

`vault.yml` and `inventory.ini` are gitignored. Keep the vault password somewhere safe (a password
manager).

**3. Install and start the portal.** Run `site.yml` again after each push to deploy the new version.

```sh
export ANSIBLE_CONFIG=$PWD/ansible.cfg   # /mnt/d is world-writable, so Ansible won't read it on its own
ansible-playbook site.yml --ask-vault-pass
```

`site.yml` does the following:
- updates Ubuntu and turns on automatic security updates
- sets the time to Asia/Dubai
- installs Docker
- checks out `portal_version` (default `main`) of the GitHub repo into `/opt/portal`, and writes
  `/opt/portal/.env` from the vault
- builds and starts the containers. The database migrations run when the backend starts.
- sets up a nightly backup at 02:30 to `/opt/portal-backups`, kept 14 days:
  `/usr/local/bin/portal-backup` dumps the database and the uploaded files.
- sets up a daily client sync at 23:55: `app.import_clients` (no path given, so it fetches live
  from Daftra, not the one-off export) rebuilds the local clients/addresses tables, picking up
  anyone added or changed in Daftra that day. Logged to `/var/log/portal-client-sync.log`.

If the repository is private, the server needs read access to it: a deploy key, or an HTTPS token
in `portal_repo`.

**4. Load the data.** Do this once, on the fresh database.

```sh
ansible-playbook import.yml --ask-vault-pass -e import_source_dir="/mnt/d/Hopa Work/Automation"
```

It copies `Proposals/`, `products.json`, `clients.json` and `Maintenance_Invoice_Items.xlsx` to the
server and runs:
1. `import_packages_from_proposals`
2. `import_maintenance_items`
3. `import_clients`
4. `create_user` for the first admin. It asks for the admin's name, email and password.

The client categories (التصنيف) are copied from Daftra by the backend itself on its first start.

The first admin login needs a code sent by email, so SMTP must work. Users and their Daftra staff
links are then set up in الإدارة.

**5. The deploy pipeline.** Once the secrets below are set, every push to `main` runs the tests and,
if they pass, updates the server (`.github/workflows/deploy.yml`). The deploy itself is
`/usr/local/bin/portal-deploy` on the server, installed by the `pipeline` role: it pulls the new
commit, rebuilds, and **goes back to the version that was running if the new one does not answer**.
Settings, uploaded files and the database are untouched. Its log is `/var/log/portal-deploy.log`,
and the same log comes back in the GitHub Actions run.

In GitHub → Settings → Secrets and variables → Actions, add three repository secrets:

| Secret | What |
|---|---|
| `SERVER_HOST` | The server's address, e.g. `51.20.114.226` |
| `SSH_PRIVATE_KEY` | The deploy key's private half, whole file including the BEGIN/END lines |
| `SSH_KNOWN_HOSTS` | The server's own key: `ssh-keyscan -t ed25519 <address>` |

The deploy key is its own key pair, not your personal one, and the server only lets it run
`portal-deploy` — no shell, no file copying, no tunnels (`roles/pipeline/tasks/main.yml`). To replace
it, make a new pair, put the public half in `portal_ci_public_key` in `group_vars/all/vars.yml`, run
`ansible-playbook site.yml --tags pipeline`, and update the secret.

Deploying by hand is still `ansible-playbook site.yml`, or `sudo portal-deploy` on the server.

### Which version is running

`VERSION` in the repo root holds the number, e.g. `1.0.0`. Bump it in the same commit as the change
it describes:

| Change | Example |
|---|---|
| A fix, nothing new | 1.0.0 → 1.0.**1** |
| Something new that breaks nothing | 1.0.1 → 1.**1**.0 |
| Something staff must be told about or retrained on | 1.1.0 → **2**.0.0 |

Nothing breaks if you forget: every deploy also stamps a **build number** (how many commits the
branch has), the commit and the time it was built, so two deploys are never confused even when the
number is the same. Those three are set by `portal-deploy`, which passes them into the image as it
builds it; an image built by hand reads as `dev`.

It is shown at the foot of the الإدارة pages — staff never see it — and returned by
`GET /api/admin/version`:

```json
{"version": "1.0.0", "build": "15", "commit": "a7c7354", "built_at": "2026-10-21 20:30"}
```

So, to see what is live: open any الإدارة page, or read the last `=== deployed` line in
`/var/log/portal-deploy.log` on the server, or the newest run in GitHub's Actions tab.

**On the server:** `ssh ubuntu@<ip>`, then `cd /opt/portal` and run any of:
- `docker compose -f docker-compose.prod.yml logs -f backend` to follow the backend's log
- `docker compose -f docker-compose.prod.yml ps` to see the containers
- `docker compose -f docker-compose.prod.yml exec backend python -m app.jobs <name>` for the other
  commands above
- `tail -f /var/log/portal-deploy.log` to watch a deploy

**HTTPS later:** point a domain at the IP. In `frontend/Caddyfile`, replace `:80` with the domain.
Open port 443 in `main.tf`, add `"443:443"` to the web service (plus a volume for Caddy's `/data`, which keeps the certificate), and set `portal_public_url` to
`https://<domain>`. Then re-run `terraform apply` and `site.yml`. Caddy gets the certificate itself.
