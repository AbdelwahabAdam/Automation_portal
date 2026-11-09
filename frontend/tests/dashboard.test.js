// node --test tests/  The periods لوحة المتابعة reads, and how a wait is written out.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { PRESETS, periodError, presetOf, rangeOf, shiftDay, uaeToday } from '../src/modules/dashboard/period.js';
import { basisDate, inPeriod } from '../src/modules/requests/queue.js';
import { formatHours, uaeDay, waited, waitedSince } from '../src/lib/format.js';
import { compare, labelEvery, nearest, niceTop, pathOf, pointsOf, ticksOf } from '../src/modules/dashboard/scale.js';

// Half past nine at night in London on 8 November is half past one in the morning of the 9th here
const LATE = Date.parse('2026-11-08T21:30:00Z');

test('today is the day it is in the UAE, not the day it is in UTC', () => {
  assert.equal(uaeToday(LATE), '2026-11-09');
  assert.equal(uaeToday(Date.parse('2026-11-08T19:59:00Z')), '2026-11-08');
});

test('a preset is the period it stands for, both days inside it', () => {
  assert.deepEqual(rangeOf('today', '2026-11-09'), ['2026-11-09', '2026-11-09']);
  assert.deepEqual(rangeOf('week', '2026-11-09'), ['2026-11-03', '2026-11-09']);
  assert.deepEqual(rangeOf('month', '2026-11-09'), ['2026-11-01', '2026-11-09']);
});

test('a week back crosses the end of a month', () => {
  assert.deepEqual(rangeOf('week', '2026-03-02'), ['2026-02-24', '2026-03-02']);
  assert.equal(shiftDay('2026-01-01', -1), '2025-12-31');
});

test('a period typed by hand is no preset, and the month is the one it opens on', () => {
  assert.equal(presetOf('2026-11-01', '2026-11-09', '2026-11-09'), 'month');
  assert.equal(presetOf('2026-11-02', '2026-11-09', '2026-11-09'), '');
  assert.deepEqual(PRESETS.map((one) => one.value), ['today', 'week', 'month']);
});

test('a period that ends before it begins is refused', () => {
  assert.equal(periodError('2026-11-01', '2026-11-09'), '');
  assert.match(periodError('2026-11-09', '2026-11-01'), /تاريخ البداية/);
  assert.match(periodError('', '2026-11-01'), /اختر/);
});

test('a wait is written the way it is read', () => {
  assert.equal(waited(0.5), 'أقل من ساعة');
  assert.equal(waited(1.2), 'ساعة');
  assert.equal(waited(2), 'ساعتان');
  assert.equal(waited(4), '4 ساعات');
  assert.equal(waited(20), '20 ساعة');
  assert.equal(waited(24), 'يوم');
  assert.equal(waited(27), 'يوم و3 ساعات');
  assert.equal(waited(51), 'يومان و3 ساعات');
  assert.equal(waited(122), '5 أيام وساعتان');
  assert.equal(waited(24 * 12), '12 يومًا');
});

test('the review time card keeps its unit', () => {
  assert.equal(formatHours(3.24), '3.2 ساعة');
  assert.equal(formatHours(0), '0 ساعة');
  assert.equal(formatHours(60), '2.5 يوم');
  assert.equal(formatHours(null), '');
});

test('a wait is counted from a moment until now', () => {
  assert.equal(waitedSince('2026-11-08T05:00:00Z', Date.parse('2026-11-09T08:00:00Z')), 'يوم و3 ساعات');
  assert.equal(waitedSince(null), '');
});

// ---------- Which requests a card's list shows ----------

const SENT = { id: 1, status: 'submitted', first_submitted_at: '2026-11-02T06:00:00Z', submitted_at: '2026-11-06T06:00:00Z' };
const APPROVED = {
  id: 2, status: 'approved', first_submitted_at: '2026-10-30T06:00:00Z', submitted_at: '2026-10-30T06:00:00Z',
  reviewed_at: '2026-11-03T06:00:00Z', first_decision_at: '2026-11-03T06:00:00Z', review_hours: 96,
};
const SELF_APPROVED = { ...APPROVED, id: 3, review_hours: null };

test('each basis reads its own moment, and none at all reads the screen\'s own', () => {
  assert.equal(basisDate(SENT, 'sent'), SENT.first_submitted_at);
  assert.equal(basisDate(SENT, 'approved'), null);
  assert.equal(basisDate(APPROVED, 'approved'), APPROVED.reviewed_at);
  assert.equal(basisDate(APPROVED, 'decided'), APPROVED.first_decision_at);
  // Decided by its own author: counted nowhere in زمن المراجعة, so it is not in that list either
  assert.equal(basisDate(SELF_APPROVED, 'decided'), null);
  assert.equal(basisDate(SENT, ''), SENT.submitted_at);
  assert.equal(basisDate({ status: 'draft', updated_at: 'x' }, ''), 'x');
});

test('a request without the moment a card counts on is not in its list', () => {
  assert.equal(inPeriod(SELF_APPROVED, 'decided', '2026-11-01', '2026-11-09'), false);
  assert.equal(inPeriod(SENT, 'approved', '', ''), false);
});

test('both ends of the period are inside it, read in UAE days', () => {
  assert.equal(inPeriod(SENT, 'sent', '2026-11-02', '2026-11-02'), true);
  assert.equal(inPeriod(SENT, 'sent', '2026-11-03', '2026-11-09'), false);
  // 20:30 UTC on the 1st is half past midnight on the 2nd here
  const late = { ...SENT, first_submitted_at: '2026-11-01T20:30:00Z' };
  assert.equal(uaeDay(late.first_submitted_at), '2026-11-02');
  assert.equal(inPeriod(late, 'sent', '2026-11-02', '2026-11-09'), true);
});

test('without dates every request of that basis is shown', () => {
  assert.equal(inPeriod(APPROVED, 'approved', '', ''), true);
  assert.equal(inPeriod(SENT, '', '', ''), true);
});

// ---------- The arithmetic behind the charts ----------

test('the axis tops out at a round number the ticks divide into', () => {
  assert.equal(niceTop(3), 4);
  assert.equal(niceTop(7), 8);
  assert.equal(niceTop(8), 8);
  assert.equal(niceTop(23), 40);
  // An empty period still draws a grid rather than a flat line on nothing
  assert.equal(niceTop(0), 4);
  assert.deepEqual(ticksOf(8), [0, 2, 4, 6, 8]);
});

test('the earliest day is on the right, as the page is read', () => {
  const points = pointsOf([1, 2, 3], { left: 0, right: 100, top: 0, bottom: 50, max: 5 });
  assert.equal(points[0].x, 100);
  assert.equal(points[2].x, 0);
  // 1 of 5 is a fifth of the way up from the bottom
  assert.equal(points[0].y, 40);
  assert.equal(pathOf(points.slice(0, 2)), 'M100 40 L50 30');
});

test('a single day sits in the middle, and nothing to count sits on the floor', () => {
  const [only] = pointsOf([0], { left: 0, right: 100, top: 0, bottom: 50, max: 0 });
  assert.equal(only.x, 50);
  assert.equal(only.y, 50);
});

test('a long period labels one day in every few', () => {
  assert.equal(labelEvery(7), 1);
  assert.equal(labelEvery(30), 5);
});

test('the pointer reads the day nearest it, counting from the right', () => {
  assert.equal(nearest(1, 10), 0);
  assert.equal(nearest(0, 10), 9);
  assert.equal(nearest(0.5, 11), 5);
  assert.equal(nearest(-3, 10), 9);
  assert.equal(nearest(0.4, 1), 0);
});

test('a period is compared with the one before it', () => {
  assert.deepEqual(compare(12, 10), { change: 2, percent: 20, direction: 1 });
  assert.deepEqual(compare(8, 10), { change: -2, percent: -20, direction: -1 });
  assert.deepEqual(compare(10, 10), { change: 0, percent: 0, direction: 0 });
  // Nothing before it: the change is told in whole orders, not as a share of zero
  assert.deepEqual(compare(3, 0), { change: 3, percent: null, direction: 1 });
  // No review time this period, or none before it: nothing to compare
  assert.equal(compare(null, 4), null);
  assert.equal(compare(4, null), null);
});
