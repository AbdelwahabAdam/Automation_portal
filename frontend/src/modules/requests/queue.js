// Which moment المراجعة reads a request by, and whether it falls inside the chosen period.
//
// A card on لوحة المتابعة counts requests by something that happened to them — first sent,
// approved, first decided on — and links here with that as `basis`. Without one, the screen goes
// by its own date as it always has: when a draft was last saved, when anything else was sent.
import { uaeDay } from '../../lib/format.js';

/** What each basis is called where the dates are typed in. */
export const BASIS_LABELS = {
  sent: 'تاريخ أول إرسال',
  approved: 'تاريخ الاعتماد',
  decided: 'تاريخ أول قرار',
};

/** The moment a request is read by under that basis, or null when it has none. */
export function basisDate(request, basis) {
  if (basis === 'sent') return request.first_submitted_at || null;
  if (basis === 'approved') return request.status === 'approved' ? request.reviewed_at : null;
  // زمن المراجعة counts only the waits it could measure: not a request still undecided, and not
  // one its own author decided — `review_hours` is empty for both
  if (basis === 'decided') {
    return request.review_hours === null || request.review_hours === undefined
      ? null : request.first_decision_at || null;
  }
  return request.status === 'draft' ? request.updated_at : request.submitted_at;
}

/**
 * Whether a request belongs to the period, read in UAE days with both ends inside it.
 * Under a basis, a request without that moment never belongs: it is not what the card counted.
 */
export function inPeriod(request, basis, from, to) {
  const moment = basisDate(request, basis);
  if (basis && !moment) return false;
  if (!from && !to) return true;
  const day = uaeDay(moment);
  if (!day) return false;
  return (!from || day >= from) && (!to || day <= to);
}
