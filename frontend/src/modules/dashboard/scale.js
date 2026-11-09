// The arithmetic behind the charts: where a point sits, and what the axis counts in.
//
// Kept apart from the drawing so it can be read and tested on its own. Everything here is in the
// chart's own coordinates (the SVG viewBox), never in screen pixels.
//
// The charts are read right to left, like the rest of the page: the earliest day is on the right.

/** The top of the axis: a round number at or above the largest value, divisible by the ticks. */
export function niceTop(max, count = 4) {
  if (!(max > 0)) return count;
  for (const power of [1, 10, 100, 1000, 10000, 100000]) {
    for (const base of [1, 2, 2.5, 5]) {
      const step = base * power;
      if (Number.isInteger(step) && step * count >= max) return step * count;
    }
  }
  return Math.ceil(max / count) * count;
}

/** The values the gridlines are drawn at, from zero up. */
export const ticksOf = (top, count = 4) => Array.from({ length: count + 1 }, (_, step) => (top / count) * step);

/**
 * Where each value sits in the plot. `index` 0 is the earliest, and it goes on the right.
 * A single point sits in the middle rather than on an edge.
 */
export function pointsOf(values, { left, right, top: edge, bottom, max }) {
  const span = right - left;
  const height = bottom - edge;
  return values.map((value, index) => ({
    x: values.length <= 1 ? left + span / 2 : right - (span * index) / (values.length - 1),
    y: bottom - (max > 0 ? (height * value) / max : 0),
    value,
    index,
  }));
}

/** A line through those points. */
export const pathOf = (points) => points.map((point, index) => `${index ? 'L' : 'M'}${round(point.x)} ${round(point.y)}`).join(' ');

const round = (number) => Math.round(number * 10) / 10;

/** One label in every how-many, so a long period does not print a label per day. */
export const labelEvery = (count, most = 7) => Math.max(1, Math.ceil(count / most));

/** Which point the pointer is nearest, from how far across the chart it is (0 at the left edge). */
export function nearest(fraction, count) {
  if (count <= 1) return 0;
  const place = Math.round((1 - Math.min(Math.max(fraction, 0), 1)) * (count - 1));
  return Math.min(Math.max(place, 0), count - 1);
}

/**
 * How this period compares with the one before it: the change, as a share of the earlier number.
 * Nothing before means nothing to compare — `percent` is null and the card says so.
 */
export function compare(now, before) {
  if (now === null || now === undefined || before === null || before === undefined) return null;
  const change = now - before;
  if (!before) return { change, percent: null, direction: Math.sign(change) };
  return { change, percent: Math.round((change / before) * 100), direction: Math.sign(change) };
}
