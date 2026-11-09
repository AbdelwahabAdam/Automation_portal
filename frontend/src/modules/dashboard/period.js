// The periods لوحة المتابعة reads, in UAE time.
//
// The office works to the UAE day, so «اليوم» means the day it is in Dubai, whatever the clock of
// the computer the page is open on says. Both ends of a period are inside it.

const DAY = 86400000;

/** Today as the office reads it: 2026-11-09. */
export function uaeToday(now = Date.now()) {
  return new Date(now + 4 * 3600 * 1000).toISOString().slice(0, 10);
}

/** The day that many days away from this one (negative goes back). */
export function shiftDay(day, days) {
  return new Date(Date.parse(`${day}T00:00:00Z`) + days * DAY).toISOString().slice(0, 10);
}

export const PRESETS = [
  { value: 'today', label: 'اليوم' },
  { value: 'week', label: 'آخر 7 أيام' },
  { value: 'month', label: 'الشهر الحالي' },
];

/** The two days a preset stands for. «الشهر الحالي» is the first of the month until today. */
export function rangeOf(preset, today = uaeToday()) {
  if (preset === 'today') return [today, today];
  if (preset === 'week') return [shiftDay(today, -6), today];
  return [`${today.slice(0, 8)}01`, today];
}

/** Which preset button a period is, if it is one of them — so it can be shown as pressed. */
export function presetOf(from, to, today = uaeToday()) {
  const found = PRESETS.find((preset) => {
    const [first, last] = rangeOf(preset.value, today);
    return first === from && last === to;
  });
  return found ? found.value : '';
}

/** What is wrong with the chosen period, if anything. */
export function periodError(from, to) {
  if (!from || !to) return 'اختر تاريخ البداية وتاريخ النهاية';
  if (from > to) return 'تاريخ البداية بعد تاريخ النهاية';
  return '';
}
