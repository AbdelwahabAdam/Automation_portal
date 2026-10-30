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
