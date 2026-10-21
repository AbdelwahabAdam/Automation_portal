# Refactor and enhancement rounds: findings

Three refactor and enhancement passes over every backend and frontend file, preceded by a test
suite so each pass could be checked. Behaviour was kept the same, including the API, the database
schema and every payload sent to Daftra. Clear bugs were fixed. Changes that would alter how
something works are listed under [Recommended, not done](#recommended-not-done) instead of made.

| Commit | What |
|---|---|
| `d6b8250` | Test suites (before any change) |
| `de1c9fb` | Round 1: backend structure, bug fixes |
| `5b1a9c9` | Round 2: frontend structure, `forms` and `daftra_sync` packages |
| `9e1ef05` | Round 3: hardening, fewer queries, clearer errors, docs |

All commits are local only. Nothing has been pushed, and the server has not been redeployed.

## How it was checked

- **Backend: 82 tests and pyflakes.** Run with `backend/run-tests.sh`, against a separate
  `portal_test` database.
  - Daftra is replaced by an in-memory fake that records every call. Network access is blocked
    inside a test, and email is caught in a list.
  - The tests pin the exact client, invoice, payment and work-order payloads of all four
    invoiced forms. They also cover resuming after a failed step, so no duplicates are created.
  - They cover validation and totals, login and two-step codes, ownership and visibility,
    attachments, review rules, admin pages, imports, and the Daftra client's retry rules.
- **Frontend: 13 tests and a production build.** Run with `frontend/check.sh` (`node --test`,
  no new dependencies).
- **Baseline first:** 61 of the backend tests were written and passed on the original code
  before anything was changed.
- **Browser check:** a headless-browser run on the local stack, with every write blocked. It
  passed on desktop and phone widths with no console errors:
  - every page renders;
  - in the new-sale form, client lookup, picking a package with the keyboard, the quantity
    stepper (the total follows) and the error summary on submit all work.
- **Real data:** the main read-only endpoints were called on the local database; all returned 200.

## Bugs fixed

| Area | Problem | Effect before the fix |
|---|---|---|
| Forms | "Not in the future" dates were checked against the server's UTC day | Between midnight and 4 a.m. UAE time, today's date was refused on submit |
| Forms | `inf`, `nan` or `1e400` were accepted as amounts (the browser also accepted `Infinity`) | The request then failed to save (server error) |
| Forms | A malformed order line or line details (not an object) | Validation and draft saving crashed (server error) |
| Attachments | A request returned for corrections accepted new files but refused to delete them | The salesperson could not remove a wrong upload |
| Attachments | The PDFs saved on approval could be deleted by the owner if the request was reopened | Now refused |
| Approval | An unexpected error midway through the Daftra steps (not a Daftra refusal) | IDs of documents already created were lost, so approving again could create a second client |
| Work order PDF | Daftra dates that include a time were reformatted wrongly | Garbled dates on the PDF |
| Uploads | A filename sent with a Windows path (`C:\Users\…\photo.jpg`) | The whole path was kept as the name |
| Login | An unknown username answered faster than a wrong password | Timing showed which usernames exist |
| Maintenance import | The match was by name *or* Daftra ID, and the ID could already belong to another product | Arbitrary match, then a unique-key crash; now name first, and an ID in use stays with its product |
| `create_user` | No checks on its input | A username with `@` can never log in; a password over 72 bytes crashed |
| Review page | The date filter compared UTC days | Requests sent after midnight UAE time fell under the previous day |
| Request view | Two separate lines of the same product were merged | The second line's details were hidden |
| Dialog | The Escape key read a stale "busy" value | Escape could cancel a confirmation while it was still working |
| Browser | Attachment blob URLs were never released | Memory grew with every file opened |
| Audit log | "Add client address" had no label, and "client" no entity type | Raw keys shown on the audit page |
| Users page | The hint named a page that no longer exists («طلبات الفريق») | Now says «المراجعة» |
| Errors | No answer from the server, or a 5xx | The user saw "Failed to fetch" or a generic message; now a clear message in Arabic |
| Catalog | An empty price was saved as 0; an empty quantity failed with a vague message | Now each says what is missing |
| README | The catalog section described the old `Products.xlsx` import | Now describes the proposals import; page names and the PDF module corrected |

## Speed and load

- **One query per list, not one per row:** the review queue, my requests, the catalog picker,
  client lookup, the users, roles and packages admin lists, and package prices. A test asserts
  each list stays within a fixed number of queries.
- **Staff list:** loaded from Daftra once instead of twice (the names and the ID list now share
  one cached call).
- **Forms page:** it downloaded every request (up to 200, with all their data) to show two
  numbers. The new endpoint `GET /api/requests/mine/counts` returns just the counts.
- **Daftra retries:** reads are tried once more on a network error, a timeout or a 502/503/504.
  Writes never are, since a lost answer may still have saved the record.

## Structure (same behaviour)

### Backend

- **`main.py` (670 lines)** now only starts the app. Its routes moved to:
  - `auth.py`: login, codes, password links;
  - `requests_api.py`: requests and attachments;
  - `lookups.py`: clients, catalog and Daftra lists for the forms.
- **`forms.py` (1,170 lines)** became a package. `app.forms` still exports the same names.
  - `options.py`: the choices;
  - `fields.py`: the building blocks;
  - `definitions.py`: the forms;
  - `validation.py`: the checks.
- **`daftra_sync.py` (660 lines)** became a package. The four flows are in its `__init__.py`.
  - `client.py`
  - `invoice.py`, which includes the receipt
  - `work_order.py`
  - `common.py`
  - One decorator replaces the four copies of the Daftra error handling.
- **`text.py`:** the helpers several modules repeated (Arabic digits, `digits()`, `squash()`,
  `display_name()`, the UAE time zone, `day_month_year()`).
- **Small additions:**
  - one error path for the Daftra list routes;
  - current names for the HTTP status constants;
  - a start-up warning when `JWT_SECRET` is shorter than 32 bytes (the local one is 17).

### Frontend

- **`RequestForm.jsx` (1,000 lines)** keeps the form's state and flow. The rest moved to `form/`:
  - `fields.jsx`: the controls;
  - `OrderLines.jsx`: the order lines;
  - `ClientLookup.jsx`: the client search, as a hook plus the note it shows.
- **Shared components and hooks:**
  - `Combobox` replaces three hand-made suggestion lists, and adds keyboard support (arrow keys,
    Enter, Escape).
  - `RequestList` is the table or card list shared by «طلباتي» and «المراجعة».
  - `useAction` replaces four busy/error helpers.
  - `useSalesData` is the sales data loading, moved out of `App.jsx`.
- **Accessibility:** dialogs and drawers keep Tab inside them, and a confirmation dialog locks
  the page behind it.
- **Styles:** inline styles became CSS classes.

## Recommended, not done

These would change behaviour or need a decision, so they were left for you. Most important first.

1. **Daftra calls run inside the approve request.**
   - Approving holds a row lock while it calls Daftra, typically 10–20 seconds; reading back a
     work order's custom fields alone waits up to 10 seconds.
   - Running the sync as a background job would free the manager's screen and make long
     timeouts harmless. The step-by-step resume already makes this safe.
2. **Logins survive a password change.**
   - A login token lasts 12 hours and is not cancelled when the password is changed or reset, so
     a stolen session keeps working after the password is changed.
   - Fix: add a "password version" to the token, as the password links already have.
3. **Lockout can be used against someone.**
   - Eight failed logins lock an account for 15 minutes, counted per account, not per IP address.
     Anyone who knows a username can keep that person locked out.
   - Fix: count per IP as well, or lock only the IP.
4. **The server runs on plain HTTP.** Passwords and login tokens cross the network unencrypted.
   A domain name would let Caddy serve HTTPS with no further changes; the README has the steps.
5. **The login token is kept in `localStorage`.** Any script injected into the page could read
   it. An httpOnly cookie avoids that; it needs a CSRF check on writes.
6. **Lists stop at a fixed number without saying so.**
   - My requests shows the latest 200 and the review queue the latest 1,000.
   - Paging on the server, or a notice when the limit is reached, would avoid silently missing
     older ones.
7. **Older import scripts.** `import_final_catalog.py`, `import_products.py` and
   `import_daftra_priced.py` are no longer the catalog's source. Running one would change the
   catalog away from the quotations. They could be removed.
8. **Uploaded files live on the server's disk.**
   - The nightly backup covers them, but losing the instance loses up to a day.
   - S3, or an EBS snapshot schedule, would be safer.
   - The server's disk is 8 GB (62% used after cleanup); 30 GB is recommended.
9. **Not possible with Daftra's API key:**
   - installment agreements;
   - attaching files to a client;
   - setting who a work order is assigned to;
   - uploading the work order's product image.

   These need Daftra's v2 write API, which refuses the API key and probably needs OAuth. Worth
   asking Daftra support.
10. **Small items:**
    - The audit log has no index on `username`; the login lockout queries by it. Fine at today's
      size.
    - The server is in eu-north-1 (Stockholm), not me-central-1 (UAE) as the Terraform files
      assume.
    - The test client warns that `httpx` is deprecated in favour of `httpx2`; harmless for now.

## Design pass (UX)

The look is unchanged: same logo, colours, typography and right-to-left layout. The work went into
how easy the screens are to use. No form field was removed: the browser check confirms that every
field of the four visible forms is on screen (33, 30, 29 and 14 fields), on desktop and phone.
These changes are local only; nothing was deployed to the server.

**Request form**

- **Progress panel** beside the form on wide screens:
  - how many sections are complete, with a progress bar;
  - every section with its state (done, in progress, not started, has errors, optional); click
    one to open it and scroll there;
  - the amounts so far (before discount, total, paid, remaining).
- **Section headers:** a completed section's number becomes a green tick.
- **«التالي»:** each section ends with a button that moves on to the next one, which saves
  hunting on a phone.
- **Action bar:** shows the progress and the total and remaining amounts next to the buttons; on
  a phone, one line.
- **Errors:** when there are errors, «الانتقال إلى أول خطأ» scrolls to and focuses the first one.
- **Unsaved changes:**
  - leaving with «رجوع» asks whether to save the draft, leave without saving, or stay;
  - closing or reloading the tab asks the browser's own question.
- **Keyboard:** search lists move with the arrow keys and pick with Enter.

**Lists, pages and dialogs**

- **Confirmations:** the browser's plain confirm boxes are now the portal's own dialogs, with
  clear wording and a red button for deletions:
  - delete draft;
  - delete user;
  - delete role, product or package;
  - send a password link;
  - turn off two-step login.
- **Users page on phone:** cards instead of a table cut off at the side.
- **Filters on phone:** the review, users and audit-log filters fold behind a «الفلاتر» button
  showing how many are set. The search stays visible.
- **Products table:**
  - 12 columns became 9: the Arabic name sits under the name, price and tax share a column, and
    the empty SKU column is hidden;
  - the edit button no longer falls off the side at 1440px.
- **Table actions:** the actions column of every table stays at the edge when a table scrolls
  sideways.
- **Request view:**
  - a summary card at the top: client, phone, code, area, the amounts (remaining in amber when
    something is due) and the Daftra document numbers;
  - on wide screens the Daftra card and history move to a side column.
- **Forms catalog:**
  - two wide cards a row;
  - the search box appears only when there are more than six forms (there are four).
- **Branding:**
  - the company logo is on the login card, and its «F» mark is in the sidebar, the phone top bar
    and the browser tab;
  - dialog buttons stack full width on a phone.
