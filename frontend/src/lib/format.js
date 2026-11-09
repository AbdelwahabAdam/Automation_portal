// How the portal writes dates and amounts, everywhere.
// The form icons and descriptions that used to live here come from the API now
// (GET /api/form-types gives each form its `icon` and `description`).

// The day an ISO time falls on here (2026-10-21), for comparing with a date picker's value
export function localDay(iso) {
  if (!iso) return '';
  const at = new Date(iso);
  return new Date(at.getTime() - at.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

export const formatDate = (iso) =>
  iso ? new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).replace(',', '') : '';

export const formatMoney = (value) => Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 });

// An amount with its unit, as the portal writes it everywhere: «8,600 درهم»
export const formatAmount = (value) => `${formatMoney(value)} درهم`;

// 2026-10-21 as it is read here: 21/10/2026 (the date box itself follows the browser's own format)
export function formatDay(day) {
  const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(day ?? ''));
  return parts ? `${parts[3]}/${parts[2]}/${parts[1]}` : '';
}

// ---------- Time as لوحة المتابعة writes it ----------

// The UAE day an ISO moment falls on (2026-11-09). The office works to that day, wherever the
// browser is: a request sent at 1am in Dubai belongs to that day, not to the evening before in UTC.
export function uaeDay(iso) {
  if (!iso) return '';
  return new Date(new Date(iso).getTime() + 4 * 3600 * 1000).toISOString().slice(0, 10);
}

// 1 -> ساعة، 2 -> ساعتان، 3 -> 3 ساعات: Arabic counts one, two and many differently
function counted(number, one, two, few, many) {
  if (number === 1) return one;
  if (number === 2) return two;
  return `${number} ${number <= 10 ? few : many}`;
}

/** How long something has been waiting, from an ISO moment until now (or until `now`). */
export function waitedSince(iso, now = Date.now()) {
  if (!iso) return '';
  return waited((now - new Date(iso).getTime()) / 3600000);
}

/** A number of hours as it is read: «ساعتان»، «20 ساعة»، «يومان و3 ساعات». */
export function waited(hours) {
  if (!(hours > 0)) return 'أقل من ساعة';
  const whole = Math.floor(hours);
  if (whole < 1) return 'أقل من ساعة';
  if (whole < 24) return counted(whole, 'ساعة', 'ساعتان', 'ساعات', 'ساعة');
  const days = Math.floor(whole / 24);
  const rest = whole % 24;
  const spelled = counted(days, 'يوم', 'يومان', 'أيام', 'يومًا');
  return rest ? `${spelled} و${counted(rest, 'ساعة', 'ساعتان', 'ساعات', 'ساعة')}` : spelled;
}

/** The زمن المراجعة card's own number: hours while they stay readable, then days. */
export function formatHours(hours) {
  if (hours === null || hours === undefined) return '';
  if (hours < 48) return `${Number(hours.toFixed(1))} ساعة`;
  return `${Number((hours / 24).toFixed(1))} يوم`;
}
