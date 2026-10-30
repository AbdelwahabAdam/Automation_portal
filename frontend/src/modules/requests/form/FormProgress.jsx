// Where the user is in a long form: how many sections are complete, each section's state (click
// to go to it), and the amounts worked out so far. Beside the form on a wide screen, and as a
// one-line summary in the action bar on a narrow one.
import { Icon, ProgressBar } from '../../../ds/index.jsx';
import { formatMoney } from '../../../lib/format.js';

// The amounts a form can show as it is filled in, in the order they are read
const TOTALS = [
  ['subtotal_amount', 'قبل الخصم'],
  ['total_amount', 'الإجمالي'],
  ['paid_amount', 'المدفوع'],
  ['remaining_amount', 'المتبقي'],
];

const STATE_LOOK = {
  done: ['check-circle', 'مكتمل'],
  error: ['alert-circle', 'يحتاج تصحيحًا'],
  partial: ['clock', 'قيد التعبئة'],
  todo: ['dot', 'لم يبدأ'],
  optional: ['minus-circle', 'اختياري'],
};

// The amounts of this form that have a value right now; none until something costs anything
export function formTotals(fieldNames, clean) {
  const totals = TOTALS.filter(([name]) => fieldNames.has(name) && typeof clean[name] === 'number')
    .map(([name, label]) => ({ name, label, value: clean[name] }));
  return totals.some((total) => total.value > 0) ? totals : [];
}

export function Totals({ totals, compact }) {
  if (!totals.length) return null;
  return (
    <dl className={compact ? 'fl-totals fl-totals--compact' : 'fl-totals'}>
      {totals.map((total) => (
        <div key={total.name} className={total.name === 'remaining_amount' || total.name === 'total_amount' ? 'fl-totals__item fl-totals__item--strong' : 'fl-totals__item'}>
          <dt>{total.label}</dt>
          <dd data-fl-num><bdi dir="ltr">{formatMoney(total.value)}</bdi> <span className="fl-totals__unit">درهم</span></dd>
        </div>
      ))}
    </dl>
  );
}

// progress: { done, total } of the sections that have required fields
export default function FormProgress({ sections, states, progress, totals, onJump }) {
  const { done, total } = progress;
  return (
    <aside className="fl-progress-rail" aria-label="تقدّم تعبئة النموذج">
      <div className="fl-progress-rail__head">
        <span className="fl-progress-rail__title">تقدّم النموذج</span>
        <span className="fl-progress-rail__count" data-fl-num>{done} من {total}</span>
      </div>
      <ProgressBar value={done} max={total} label={`اكتمل ${done} من ${total} أقسام`} />
      <ol className="fl-progress-rail__list">
        {sections.map((section, index) => {
          const [icon, label] = STATE_LOOK[states[index]];
          return (
            <li key={section.title}>
              <button type="button" className={`fl-progress-rail__item fl-progress-rail__item--${states[index]}`} onClick={() => onJump(index)}>
                <span className="fl-progress-rail__icon"><Icon name={icon} size={16} label={label} /></span>
                <span className="fl-progress-rail__name">{section.title}</span>
              </button>
            </li>
          );
        })}
      </ol>
      {totals.length > 0 && (
        <div className="fl-progress-rail__totals">
          <Totals totals={totals} />
        </div>
      )}
    </aside>
  );
}
