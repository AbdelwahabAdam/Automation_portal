// The two charts on لوحة المتابعة, drawn by hand in SVG — no chart library, the design system's
// own colours, and the page's own direction: the earliest day is on the right.
//
// Every chart carries a table of the same numbers behind «عرض كجدول», so nothing is reachable only
// by hovering: the tooltip adds, it never gates.
import { useRef, useState } from 'react';
import { Button } from '../../ds/index.jsx';
import { formatDay } from '../../lib/format.js';
import { labelEvery, nearest, niceTop, pathOf, pointsOf, ticksOf } from './scale.js';

// Checked with the skill's validator against the white surface: ΔE 27.3 under deuteranopia,
// 30.3 to normal vision. They are the portal's own status hues, so a sent order is the blue it is
// in «قيد المراجعة» and an approved one the green of «معتمد».
export const SERIES = {
  submitted: { label: 'المرسلة', color: 'var(--fl-blue-600)' },
  approved: { label: 'المعتمدة', color: 'var(--fl-green-600)' },
};

// The plot's own coordinates. The width is nominal: the SVG scales to its card.
const VIEW = { width: 720, height: 240 };
const PAD = { top: 12, right: 34, bottom: 26, left: 8 };
const PLOT = {
  left: PAD.left, right: VIEW.width - PAD.right, top: PAD.top, bottom: VIEW.height - PAD.bottom,
};
const TICKS = 4;

/** Where a point sits across the plot, kept off the edges so the readout is never half cut off. */
const across = (x) => Math.min(Math.max((x / VIEW.width) * 100, 14), 86);

/** The frame every chart sits in: its name, what it is, a legend, and the table behind it. */
function ChartCard({ title, subtitle, legend, table, children }) {
  const [asTable, setAsTable] = useState(false);
  return (
    <section className="fl-card fl-chart" aria-label={title}>
      <div className="fl-chart__head">
        <div>
          <h2 className="fl-chart__title">{title}</h2>
          <p className="fl-flush fl-small fl-muted">{subtitle}</p>
        </div>
        <Button size="sm" variant="ghost" icon={asTable ? 'grid' : 'file'} onClick={() => setAsTable(!asTable)}>
          {asTable ? 'عرض كرسم' : 'عرض كجدول'}
        </Button>
      </div>
      {legend}
      {asTable ? <div className="fl-table-scroll fl-table-scroll--bounded">{table}</div> : children}
    </section>
  );
}

function Legend({ names }) {
  return (
    <ul className="fl-legend" role="list">
      {names.map((name) => (
        <li key={name}>
          <span className="fl-legend__key" style={{ background: SERIES[name].color }} aria-hidden="true" />
          {SERIES[name].label}
        </li>
      ))}
    </ul>
  );
}

/**
 * The period day by day: how many were sent, how many approved. Two lines, one axis.
 * Hovering anywhere over a day reads out both of them.
 */
export function TrendChart({ trend, from, to }) {
  const [at, setAt] = useState(null);
  const area = useRef(null);
  if (!trend.length) {
    return (
      <ChartCard title="الحركة اليومية" subtitle="الفترة المختارة طويلة جدًا لرسمها يومًا بيوم">
        <p className="fl-chart__empty">اختر فترة أقصر لرؤية الحركة اليومية.</p>
      </ChartCard>
    );
  }
  const most = Math.max(...trend.flatMap((row) => [row.submitted, row.approved]));
  const max = niceTop(most, TICKS);
  const lines = Object.keys(SERIES).map((name) => ({
    name, points: pointsOf(trend.map((row) => row[name]), { ...PLOT, max }),
  }));
  const every = labelEvery(trend.length);
  const shown = at === null ? null : trend[at];

  const follow = (event) => {
    const box = area.current.getBoundingClientRect();
    setAt(nearest((event.clientX - box.left) / box.width, trend.length));
  };

  return (
    <ChartCard
      title="الحركة اليومية"
      subtitle={`من ${formatDay(from)} إلى ${formatDay(to)} — أول إرسال واعتماد في كل يوم`}
      legend={<Legend names={['submitted', 'approved']} />}
      table={(
        <table className="fl-table">
          <thead><tr><th>اليوم</th><th>المرسلة</th><th>المعتمدة</th></tr></thead>
          <tbody>
            {trend.map((row) => (
              <tr key={row.day}>
                <td className="fl-cell--nowrap"><bdi dir="ltr">{formatDay(row.day)}</bdi></td>
                <td data-fl-num>{row.submitted}</td>
                <td data-fl-num>{row.approved}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    >
      <div className="fl-chart__plot" ref={area}>
        <svg viewBox={`0 0 ${VIEW.width} ${VIEW.height}`} className="fl-chart__svg" role="img"
          aria-label={`الحركة اليومية: ${trend.length} يومًا، أعلى قيمة ${most}`}
          onPointerMove={follow} onPointerDown={follow} onPointerLeave={() => setAt(null)}>
          {ticksOf(max, TICKS).map((value) => {
            const y = PLOT.bottom - ((PLOT.bottom - PLOT.top) * value) / max;
            return (
              <g key={value}>
                <line x1={PLOT.left} x2={PLOT.right} y1={y} y2={y} className="fl-chart__grid" />
                <text x={PLOT.right + 6} y={y + 4} className="fl-chart__tick">{value}</text>
              </g>
            );
          })}
          {trend.map((row, index) => {
            if (index % every) return null;
            const x = lines[0].points[index].x;
            return (
              <text key={row.day} x={x} y={VIEW.height - 8} className="fl-chart__tick" textAnchor="middle">
                {Number(row.day.slice(8, 10))}
              </text>
            );
          })}
          {shown && (
            <line className="fl-chart__crosshair" x1={lines[0].points[at].x} x2={lines[0].points[at].x}
              y1={PLOT.top} y2={PLOT.bottom} />
          )}
          {lines.map((line) => (
            <path key={line.name} d={pathOf(line.points)} fill="none" strokeWidth="2" strokeLinejoin="round"
              strokeLinecap="round" stroke={SERIES[line.name].color} />
          ))}
          {/* Markers only while there is room for them; on a long period the line itself is the shape */}
          {trend.length <= 14 && lines.flatMap((line) => line.points.map((point) => (
            <circle key={`${line.name}-${point.index}`} cx={point.x} cy={point.y} r="4"
              fill={SERIES[line.name].color} className="fl-chart__dot" />
          )))}
          {shown && lines.map((line) => (
            <circle key={`${line.name}-on`} cx={line.points[at].x} cy={line.points[at].y} r="5"
              fill={SERIES[line.name].color} className="fl-chart__dot" />
          ))}
        </svg>
        {shown && (
          <div className="fl-tip" style={{ left: `${across(lines[0].points[at].x)}%` }}>
            <div className="fl-tip__day"><bdi dir="ltr">{formatDay(shown.day)}</bdi></div>
            {Object.keys(SERIES).map((name) => (
              <div key={name} className="fl-tip__row">
                <span className="fl-tip__key" style={{ background: SERIES[name].color }} aria-hidden="true" />
                <span className="fl-tip__value" data-fl-num>{shown[name]}</span>
                <span className="fl-tip__name">{SERIES[name].label}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </ChartCard>
  );
}

/**
 * Where the period's work came from: one bar per form, the busiest first.
 * One series, so no legend — the title says what is counted. A bar opens its own form's list.
 */
export function FormBars({ rows, onPick }) {
  const most = Math.max(1, ...rows.map((row) => row.submitted));
  return (
    <ChartCard
      title="حسب نوع النموذج"
      subtitle="الطلبات المرسلة خلال الفترة — اختر نموذجًا لتصفية اللوحة عليه"
      table={(
        <table className="fl-table">
          <thead><tr><th>نوع النموذج</th><th>المرسلة</th><th>المعتمدة</th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <td className="fl-cell--wrap">{row.label}</td>
                <td data-fl-num>{row.submitted}</td>
                <td data-fl-num>{row.approved}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    >
      {!rows.length ? (
        <p className="fl-chart__empty">لا توجد طلبات مرسلة في هذه الفترة.</p>
      ) : (
        <ul className="fl-bars" role="list">
          {rows.map((row) => (
            <li key={row.key}>
              <button type="button" className="fl-bars__row" onClick={() => onPick(row.key)}
                title={`${row.label}: ${row.submitted} مرسلة، ${row.approved} معتمدة`}>
                <span className="fl-bars__name">{row.label}</span>
                <span className="fl-bars__track">
                  <span className="fl-bars__fill" style={{ inlineSize: `${(row.submitted / most) * 100}%` }} />
                </span>
                <span className="fl-bars__value" data-fl-num>{row.submitted}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </ChartCard>
  );
}
