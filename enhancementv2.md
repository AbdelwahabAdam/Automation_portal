# Enhancements, round two: what is left

The first five of the agreed list are done and committed (`cc6cd86`): readable dates and amounts,
corner messages, better uploads, and loading shapes. This file is the plan for the remaining
seven, so the work can be picked up in any order.

Each one says what a user would notice, why it is worth doing, what it touches, and what could
go wrong. Nothing here has been built.

**Suggested order:** 6 and 7 first (they protect work and catch mistakes early), then 8, then 9
and 10 for managers, and 11 and 12 last, since those two need decisions from you.

| # | What | Size | Needs a decision from you |
|---|---|---|---|
| 6 | Autosave drafts | Small | No |
| 7 | Errors while typing | Small | No |
| 8 | Counts in the menu | Small | No |
| 9 | Faster review | Medium | No |
| 10 | Client history | Medium | Yes — which fields to show |
| 11 | Home page | Large | Yes — what it shows, who lands on it |
| 12 | Install on the phone | Small | Yes — the app's icon |

---

## 6. Autosave drafts

**What staff would see.** The form saves itself a few seconds after they stop typing, with a quiet
«حُفظ» beside the request number. Nothing is lost if the phone dies, the battery runs out, or the
tab is closed. The question "you have unsaved changes" on leaving mostly disappears, because there
is nothing unsaved.

**Why.** A new sale has 33 fields. Losing them part-way is the worst thing that can happen to a
salesperson on a phone, and today it is one closed tab away.

**How.** `RequestForm.jsx` already knows whether anything changed (`dirty`) and already saves a
draft. Add a timer: three seconds after the last change, if the request is a draft or returned,
save quietly. Show the state next to the request number: «جارٍ الحفظ…» / «حُفظ 12:40». Keep the
manual button, since people trust it.

**Watch out for.** Only ever autosave a draft, never submit. Do not autosave while a save is
already running, or the two answers can arrive out of order. The first autosave creates the
request, so it must not run twice at once and make two requests. An autosave that fails should be
quiet and try again, not interrupt with a red message.

**Touches.** `frontend/src/RequestForm.jsx` only. No backend change: `PUT /api/requests/{id}` with
`action: "draft"` already does exactly this.

---

## 7. Errors while typing

**What staff would see.** A wrong phone number or a missing required field is flagged as soon as
they leave the field, not after pressing «إرسال للمراجعة». Fields they have not reached yet stay
quiet.

**Why.** Today a form with 10 mistakes shows all 10 at the end, which is discouraging and means
scrolling back through nine sections.

**How.** The form already works out every error on each keystroke (`evaluateForm`). What is missing
is deciding *when* to show one. Keep a set of "fields the user has finished with", add a field to it
on blur, and show the error only for those (plus every error after a failed submit, as now).

**Watch out for.** Do not flag a field while it is being typed in — only after leaving it. A field
the user has not touched must stay quiet, or a new form turns red immediately. The section states
in the progress panel should not turn red from this.

**Touches.** `frontend/src/RequestForm.jsx`, and the `Field` component if the styling needs it.

---

## 8. Counts in the menu

**What staff would see.** A number next to «المراجعة» for managers (requests waiting) and next to
«طلباتي» for sales (requests sent back for corrections), in the sidebar and the phone bar.

**Why.** Today a manager has to open the review page to find out whether anything is waiting. A
salesperson does not learn that a request came back until they look.

**How.** `GET /api/requests/mine/counts` already exists. Add the same for review
(`GET /api/review/counts`, how many are submitted). Load both in `App.jsx` where the pages are
known, refresh every couple of minutes and after a decision, and pass the number to the menu item.

**Watch out for.** The number must not become stale after approving or returning something. Only
ask for counts the user can actually see, so a salesperson never calls the review endpoint.

**Touches.** `backend/app/review.py` (one small endpoint), `frontend/src/App.jsx`,
`frontend/src/pages.jsx`, the nav styles.

---

## 9. Faster review

**What managers would see.** Clicking a request in the review list opens it in a panel beside the
list instead of replacing the page. Approve or return it there, and it moves to the next waiting
request without going back and forth.

**Why.** A manager reviewing ten requests today does ten round trips through a list that reloads
each time. This is the single biggest time saving for them.

**How.** The pieces exist: `RequestView` renders a request, `Drawer` is a side panel, and the list
is already its own component. Render the view inside a drawer on a wide screen (keep the full page
on a phone, where a panel has no room). After a decision, move to the next request in the list and
show its number («3 من 7»), with ← → to move between them.

**Watch out for.** The decision must still be tied to the revision on screen, as it is now. Reading
a long request inside a panel must not become cramped: below about 1,200px, keep the full page.

**Touches.** `frontend/src/Review.jsx`, `frontend/src/RequestView.jsx` (so it can render inside a
panel), styles. No backend change.

---

## 10. Client history

**What staff would see.** When a client is found by phone or code, a line appears: their last
requests and anything still owed, e.g. «3 طلبات سابقة · فاتورة 06273 متبقٍ 4,650 درهم».

**Why.** A salesperson about to sell a maintenance contract cannot currently tell whether the
client already has one, or owes money on an earlier invoice.

**How.** The portal already fetches the client's open invoices from Daftra for the balance-payment
form (`GET /api/daftra/clients/{id}`). Add their recent portal requests to the same answer, and
show both under the client fields.

**Decide first.** What should it show: only this salesperson's requests or everyone's; how far
back; and whether it should warn when an invoice is overdue.

**Watch out for.** It must not slow the client search down: load it after the client is filled in,
not before. A salesperson should not learn a colleague's commission or anything they should not
see — the list should stay to facts about the client.

**Touches.** `backend/app/lookups.py`, `frontend/src/form/ClientLookup.jsx`.

---

## 11. Home page

**What staff would see.** A first screen after signing in.
For a manager: how many requests are waiting, today's requests, the amounts approved this week.
For a salesperson: their own month — requests sent, approved, returned, and the total they sold.

**Why.** Today, signing in lands on a list of forms, and nobody can see how the week is going
without counting by hand.

**Decide first (the main reason this is last).**
- Which numbers matter to you? Mine are a guess.
- Who lands on it: everyone, or only managers?
- Does it show money per salesperson? That makes it a performance board, which changes how the
  team feels about it.

**How.** A new endpoint returning a handful of counts and sums over the requests table, and a new
page with stat tiles and a short list of what needs attention. The design system has the pieces.

**Watch out for.** Only approved requests should count as sales. Amounts should come from the
request's own total, not be recalculated. The page must stay fast as the number of requests grows —
counting in the database, not by loading every request.

**Touches.** A new backend module, a new page, the navigation, the design system.

---

## 12. Install on the phone

**What staff would see.** «Add to home screen» in the phone's browser gives the portal its own icon
and opens it full screen, without the browser's address bar, like an app.

**Why.** Sales staff use it on a phone all day. It saves them finding a tab and gives more room.

**How.** A small `manifest.json` (name, colours, icons) and a link to it in `index.html`. Icons at
192 and 512px from the company logo. No service worker and no offline support — those need care
and would deserve their own round.

**Decide first.** The icon. The current mark is the logo's «F» on white; a phone icon usually looks
better as the mark on the brand's navy, with rounded corners. I can make it from the existing logo
if you like.

**Watch out for.** Without a service worker it still needs a connection, as it does today — it will
not work offline, and should not look as if it does.

**Touches.** `frontend/public/`, `frontend/index.html`.

---

## How to check any of these

Same three checks as the rest of the portal (see the README):

```
sh backend/run-tests.sh      # 83 tests and pyflakes
sh frontend/check.sh         # 14 tests and the production build
sh frontend/ui-check/run.sh  # the browser, desktop and phone widths
```

The browser check confirms, among other things, that every field of every visible form is still on
screen — the rule that no form field is ever removed.
