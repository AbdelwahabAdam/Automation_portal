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

## Users, roles and pages

The first admin is created from the command line (from `backend/`):

```
.venv\Scripts\python -m app.create_user <username> <password> --admin --name "Full Name" --email you@example.com
```

Everything after that is done in the portal, under the الإدارة tab:

- **المستخدمون** — add users, edit them, stop an account, send a link to set a new password.
- **الأدوار والصلاحيات** — roles. A role is a list of pages; a user opens the pages of all their roles.
- **سجل النشاط** — every login, change and file download, with the values before and after.

A new user gets an email with a link to set their own password (valid 72 hours, single use),
and then logs in with their email or username. "نسيت كلمة المرور؟" on the login screen and
"رابط كلمة المرور" in the users table send the same kind of link. If an email cannot be sent,
the admin is shown the link to pass on by hand.

A user can be made manager of one or more departments. A manager opens every page of the
department, including its manager pages (marked `"manager": True` in `pages.py`, e.g. المراجعة
in sales), which cannot be put in a role.

Every user has a حسابي page (their name in the header): name, password and two-step login.
Two-step login is a 6-digit code emailed after the password (valid 10 minutes, single use).
It is always on for admins and a choice for everyone else, so an admin must have an email
and email must be working. If it is not, `REQUIRE_ADMIN_MFA=false` in `backend/.env` lets
admins in with the password alone until it is fixed.

A user with no requests can be deleted; one with requests can only be stopped, because a request
keeps its owner. Eight failed logins on one account block it for 15 minutes.

An admin opens every page. The admin pages are for admins only and cannot be put in a role.

Pages are listed in `backend/app/pages.py`, grouped by department. To add one, add it
there and map its key to a screen in `frontend/src/pages.jsx`; a page with no screen
yet shows as a blank page with its label. Protect its API routes with `require_page("<key>")`.

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
.venv\Scripts\python -m app.import_packages_from_proposals --dry-run
.venv\Scripts\python -m app.import_packages_from_proposals
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

Approving one of these requests creates its documents in Daftra (`app/daftra_sync/`). The invoice PDF and
the receipt PDF are attached to the request. The receipt and work order PDFs are drawn by the portal
(`app/printouts.py`, templates in `app/templates/pdf/`), since Daftra's API has none:

- **طلب بيع لعميل جديد**: the client when new, the invoice, and the receipt (سند قبض) for the amount paid.
  When «إنشاء أمر الشغل» is نعم, it also creates the installation work order, and attaches a PDF of it
  drawn by the portal:
  - with the approving manager written in it as «المسؤول» (Daftra's API cannot set who a work order is
    for: it records the API user as its creator);
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
    `.venv\Scripts\python -m app.import_maintenance_items`.

The forms' «التصنيف» (Daftra's client categories, each with the المنطقة and الإمارة it fills in) is read from
our own `client_categories` table, never from Daftra on a request. The portal fills the table once, the first
time it starts with it empty. To refresh it after categories change in Daftra, run the following from
`backend/` (it reads every client, so it takes a few minutes):

```
.venv\Scripts\python -m app.import_client_categories
```

Other form types are not sent to Daftra yet. Before it works for a salesperson:

- Link their portal user to their Daftra staff member (الإدارة → المستخدمون → الموظف في دفترة); it is the
  sales person on the invoice.
- Every product in the order needs its Daftra id (`daftra_id`, set by `import_packages_from_proposals`).

If Daftra refuses or cannot be reached, the request is not approved and the manager sees why. Approving
again continues from the step that failed. The invoice's `po_number` and the payment's notes carry
`PORTAL-<request id>`, so neither is ever created twice.

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

Form types and their fields live in `backend/app/forms/definitions.py`, written with the
building blocks in `fields.py` and the choices in `options.py`. The frontend renders whatever
the definitions say, and `validation.py` checks a submission against them.
`frontend/src/validation.js` repeats the same checks for instant feedback.

## Code layout

Backend (`backend/app/`):

- `main.py` starts the app and includes the routers: `auth.py` (login, two-step codes, password
  links), `requests_api.py` (a salesperson's requests and attachments), `lookups.py` (clients,
  catalog and Daftra lists for the forms), `review.py` (approve or return), `account.py`,
  `admin.py` and `catalog.py` (the admin pages).
- `forms/` — the form definitions and their validation; `daftra.py` — the Daftra API client and
  its cached lists; `daftra_sync/` — what approving creates in Daftra (client, invoice and
  receipt, work order); `printouts.py` — the PDFs the portal draws; `mail.py` and
  `templates/email/` — the emails; `text.py` — small shared helpers (Arabic digits, UAE time).
- `import_*.py`, `create_user.py` — command-line jobs (`python -m app.<name>`).

Frontend (`frontend/src/`): `App.jsx` (layout and navigation), `pages.jsx` (which screen each
page key opens), `Sales.jsx` + `RequestForm.jsx` + `form/` (the forms), `RequestList.jsx`,
`RequestView.jsx`, `MyRequests.jsx`, `Review.jsx`, `admin/` (the admin pages), `ds/` (the design
system's components, tokens and styles), `api.js` (calls to the backend).

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

**On the server:** `ssh ubuntu@<ip>`, then `cd /opt/portal` and run any of:
- `docker compose -f docker-compose.prod.yml logs -f backend` to follow the backend's log
- `docker compose -f docker-compose.prod.yml ps` to see the containers
- `docker compose -f docker-compose.prod.yml exec backend python -m app.<command>` for the other
  commands above
- `tail -f /var/log/portal-deploy.log` to watch a deploy

**HTTPS later:** point a domain at the IP. In `frontend/Caddyfile`, replace `:80` with the domain.
Open port 443 in `main.tf`, add `"443:443"` to the web service (plus a volume for Caddy's `/data`, which keeps the certificate), and set `portal_public_url` to
`https://<domain>`. Then re-run `terraform apply` and `site.yml`. Caddy gets the certificate itself.
