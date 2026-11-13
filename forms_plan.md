# Forms refactor: one file for the fields, one for the output

**Done 2026-11-13** — all six steps. Every form folder is `__init__.py`, `fields.py` and (for the 7 that
create something in Daftra) `output.py`; no `definition.py` or `hooks.py` is left. Full backend suite
467 passed, `check.sh` and `ui-check` clean apart from three pre-existing local-catalog complaints.

Agreed 2026-11-13. Every form folder ends up with the same two files:

```
app/forms/<key>/
├── __init__.py     the FormSpec: key, label, icon — unchanged
├── fields.py       what the form asks: its sections, one switch per field
└── output.py       what approving it sends to Daftra: one function per document
```

`output.py` exists only for the 7 forms that create something in Daftra (new_sale, online_sale,
quotation, maintenance, contract_renewal, balance_payment, tech_extra_works). The other 13 have
`fields.py` alone.

## The three decisions

| Question | Decided |
|---|---|
| How a field is switched | One switch, three values: `HIDE`, `SHOW`, `REQUIRED` |
| How an output function is written | Explicit mapping: each Daftra field assigned from a form field |
| Rollout | طلب بيع and عرض سعر first; the other 18 after they are looked at |

## The rule that governs all of it

**Nothing a user sees and nothing Daftra receives may change.** This is a change of shape, not of
behaviour. Two guards make that checkable rather than hoped for:

1. **A snapshot of every form's fields**, taken from today's code before anything moves. The
   browser is sent `sections` as JSON; that JSON is saved per form and compared on every run. A
   refactored form passes only if its JSON is identical, key for key.
2. **The Daftra payload tests that already exist** (`tests/modules/requests/test_review.py` and
   the per-form tests) pin the exact body of every invoice, receipt, estimate and work order.
   They must pass untouched — a test that needs editing means behaviour changed.

---

## Part 1 — fields

### The switch

```python
HIDE, SHOW, REQUIRED          # the three values
REQUIRED_IF(condition)        # required only when something else is true
```

`REQUIRED_IF` is needed because some rules are not on/off: «اسم الخصم» is required only when a
discount is given, «مدة التركيب» only when a work order is wanted. Today these are `required_if=`.

### A section is a function with one argument per field

In `modules/form_engine/sections.py`, replacing the behaviour flags of today's `fields.py`:

```python
def client(*, phone, phone2, client_code, customer_name, customer_type, gender, email,
           labels=None, note=None):
```

- **Keyword-only, and every field must be named.** A form that forgets one fails when the app
  starts, not when a customer opens it. A misspelt field name fails the same way.
- **`labels=`** for wording that differs per form («تاريخ الطلب» / «تاريخ الاتفاق مع العميل»,
  «اسم العميل» / «اسم العميل / الجهة المطلوب على عرض السعر»).
- **What a field *is* stays inside the function**: its type, pattern, max length, the phone search,
  the location-link rule. A form decides whether it appears and whether it is required — not how a
  phone number is validated.

The shared sections, by how many forms use them:

| Section | Forms | Fields it switches |
|---|---|---|
| `request_info` بيانات الطلب | 18 | request_date, employee_name, order_source / source |
| `client` بيانات العميل | 18 | phone, phone2, client_code, customer_name, customer_type, gender, email |
| `address` عنوان الخدمة | 11 | category, area, emirate, street, house, location_url, coordinates |
| `amounts` قيمة الطلب | 7 | subtotal_amount, total_amount, discount_label, discount_amount, discount_approved_by, paid_amount, remaining_amount, remaining_due_date |
| `payment` تفاصيل الدفعة | 9 | payment_method, treasury, payment_date, payment_reference, collector_name |
| `attachments` المرفقات | 18 | per form — already a list of files |
| `notes` ملاحظات | 19 | notes |

A section only one form has (طلب بيع's «تفاصيل الطلب» with its colours and inscription, الصيانة's
devices and services) is written in that form's own `fields.py`, as a function of its own.

### What does not fit a switch, and where it goes

- **Computed fields** (`total_amount` from subtotal and discount, `remaining_amount`). Whether one
  is shown is a switch; *how* it is computed follows from which of its inputs are shown. `amounts`
  works that out, and refuses a combination that cannot be computed (a total with no subtotal).
- **`must_pay`, `must_equal`** (الصيانة is paid in full). An argument of `amounts`, beside the switches.
- **`validate`** (تسديد مبلغ متبقي: not more than the invoice still owes). It is a rule about the
  fields, so it moves from `hooks.py` to `fields.py`.

---

## Part 2 — output

### One function per document, each returning what goes in it

```python
# app/forms/new_sale/output.py
def client(ctx):      ...   # العميل: created when new, kept in step when known
def invoice(ctx):     ...   # الفاتورة
def receipt(ctx):     ...   # سند القبض
def work_order(ctx):  ...   # أمر الشغل — returns None when the form did not ask for one

DOCUMENTS = [client, invoice, receipt, work_order]    # the order they are made in
```

Each returns a small typed object — `Invoice`, `Receipt`, `WorkOrder`, `Estimate`, `ClientRecord` —
whose attributes are Daftra's own fields. Returning `None` means «not for this request».

### Who does what

| The form's `output.py` decides | `modules/invoicing` keeps |
|---|---|
| Which documents are made, and in what order | Making each one once, however often it is approved |
| Which form field fills which Daftra field | Picking up after a failure from the step that failed |
| What is left empty on purpose | Finding a lost document again by its marker |
| When a document is not made at all | `is_offline`, store, branch, tax, currency |
| | Checking Daftra's total against the request's |
| | Saving the PDFs on the request |

So `ensure_invoice(request, items, staff_id)` — which reads `request.data` itself — becomes
`ensure_invoice(request, document)`, which is handed what to send. The same for the receipt, the
estimate and the work order.

### The pieces a form builds from

Explicit mapping does not mean rewriting the hard parts seven times. These stay shared, and a
form calls them inside its own function:

- `order_lines(ctx)` — the invoice lines from المنتجات والباقات, the inscription line included
- `service_address(data)` — the address printed on the document
- `package_terms(ctx)` — the terms its packages print
- `cooler_work_order_fields(ctx)` — the work order's custom fields (colours, cover back, verse…)

That last one matters: طلب بيع and طلب بيع - دفع إلكتروني make the same work order, and forms may
not import each other. The mapping lives in `invoicing`; each form's `work_order()` calls it and
may change any value before returning.

### What else moves into `output.py`

- **The form's actions** after approval (دفع إلكتروني: «إنشاء أمر الشغل», «إعادة إرسال الفاتورة») —
  they create output, so they sit beside it.
- **The invoice email to the client** (دفع إلكتروني) — `def client_email(ctx)`, one more entry in
  `DOCUMENTS`. It is the portal's own email; Daftra sends nothing, as proven on 2026-11-13.

---

## The steps

Each step ends with the scoped tests green and nothing committed — the tree is left for review.

**Step 0 — the safety net.** Before any code moves: `tests/forms/test_fields_snapshot.py` and one
saved JSON per form, generated from today's code. Run it once to prove it passes as things are.

**Step 1 — the section library.** `modules/form_engine/sections.py`: the three values,
`REQUIRED_IF`, and the seven section functions. The old helpers stay, untouched, so the 18 forms
not yet moved keep working. Unit tests for the switches themselves: `HIDE` removes the field,
`REQUIRED` marks it, an unnamed or unknown field is refused.

**Step 2 — pilot, fields.** `new_sale/definition.py` → `fields.py`, `quotation/definition.py` →
`fields.py`. Their snapshots must not change by a character.

**Step 3 — the document objects.** `modules/invoicing/documents.py` with `Invoice`, `Receipt`,
`WorkOrder`, `Estimate`, `ClientRecord`, and a runner that takes `DOCUMENTS` and makes them in
order. `ensure_*` change to take a document. Until a form is moved, an adapter builds the document
from `request.data` exactly as today, so the 5 forms not yet moved are unaffected.

**Step 4 — pilot, output.** `new_sale/hooks.py` → `output.py`, `quotation/hooks.py` → `output.py`.
Every pinned payload test passes untouched.

**⏸ Stop here.** You read the two pilot forms. Anything about the shape that reads wrong is
changed now, while it costs two files instead of twenty.

**Step 5 — the rest.** Output for the other 5 Daftra forms (maintenance, contract_renewal,
balance_payment, tech_extra_works, online_sale), then fields for the other 18. One form at a time,
each checked against its snapshot.

**Step 6 — clear out.** Delete the old helpers and the adapter. Rename the two outside references
(`tests/forms/test_tech_extra_works.py`, `test_review.py`). Extend `test_architecture.py`: every
form folder has `fields.py`; it has `output.py` exactly when it creates something in Daftra; none
has `definition.py` or `hooks.py`. Rewrite «adding a form» in `README.md` and `ARCHITECTURE.md`,
and the layout in `final_plan.md`.

**Final check.** The full backend suite once, `frontend/check.sh`, and `ui-check/run.sh` — whose
«every field of every visible form is on the screen» pass is the last proof the browser sees what
it saw before.

---

## What this does not do

- **No change to the frontend.** It receives the same `sections` JSON.
- **No change to stored requests.** Field names are untouched, so every old request reads as before.
- **No new behaviour.** Making a field optional that is required today, or putting something new
  on an invoice, is a separate change made *after* — in one line of one file, which is the point.

## Risks

- **A field hidden in `fields.py` but still read in `output.py`.** Hiding «الخزينة» on a form whose
  receipt needs it would fail at اعتماد, not when the form is saved. A start-up check compares the
  two: every form field an output function reads must be one the form shows.
- **The work order is the heaviest mapping** (14 custom fields, list entries spelt to the letter,
  a PDF the portal draws from the same values). It moves last within the pilot, and its PDF is
  compared before and after.
- **Seven sections serving twenty forms** will show up inconsistencies that exist today. Three
  forms write their own «تفاصيل الدفعة» by hand instead of calling `payment` (balance_payment,
  maintenance, tech_cash_collection), seven write their own «قيمة الطلب», and two their own
  «بيانات العميل». Each is moved onto the shared section where the switches can express it, and
  kept as the form's own section where they cannot. Either way the snapshot decides, and the
  differences are listed for you at the end — not quietly tidied.
