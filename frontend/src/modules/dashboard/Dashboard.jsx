// لوحة المتابعة: what moved in the chosen period, and what is still waiting on someone.
//
// The filters live in the URL, so coming back from a request leaves the page as it was found and
// a view of it can be sent to someone else. One call draws everything, so all five numbers and
// the list below them are of the same moment — which the page says.
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import * as dashboardApi from '../../api/dashboard.js';
import {
  Alert, Badge, Button, EmptyState, Field, Filters, Icon, PageHeader, Select, Skeleton, Tabs, TextInput,
} from '../../ds/index.jsx';
import { formatDate, formatDay, formatHours, waitedSince } from '../../lib/format.js';
import { FormBars, TrendChart } from './charts.jsx';
import { PRESETS, periodError, presetOf, rangeOf, uaeToday } from './period.js';
import { compare } from './scale.js';

// The page reads itself again this often, so a decision taken elsewhere shows without a refresh
const REFRESH_MS = 60 * 1000;

// How «محتاج متابعة منك» can be ordered. The server does the ordering: only the first rows are
// sent, so sorting what arrived would answer «الأحدث» with the newest of the oldest.
const SORTS = [
  { value: 'oldest', label: 'الأقدم في الانتظار' },
  { value: 'newest', label: 'الأحدث في الانتظار' },
];

const TABS = [
  { value: 'all', label: 'الكل' },
  { value: 'submitted', label: 'بانتظار المراجعة' },
  { value: 'returned', label: 'بانتظار التعديل' },
];

// The five cards, in the order they are read. `period` says whether the dates apply to it: the
// two backlog cards are about now, whenever the work was sent.
const CARDS = [
  {
    key: 'submitted', title: 'الطلبات المرسلة', icon: 'send', period: true, sub: 'أول إرسال خلال الفترة',
    info: 'عدد الطلبات التي أُرسلت لأول مرة خلال الفترة. حفظ مسودة أو إعادة إرسال طلب مُعاد لا يُحتسب إرسالًا جديدًا.',
    opens: { tab: 'all', basis: 'sent' },
  },
  {
    key: 'approved', title: 'الطلبات المعتمدة', icon: 'check-circle', period: true, sub: 'اعتُمدت خلال الفترة',
    info: 'عدد الطلبات التي اعتُمدت خلال الفترة، بما فيها طلبات أُرسلت قبلها.',
    opens: { tab: 'approved', basis: 'approved' },
  },
  {
    key: 'awaiting_review', title: 'بانتظار المراجعة', icon: 'clock', period: false, sub: 'كل الطلبات المنتظرة الآن',
    info: 'الطلبات المرسلة التي تنتظر قرار المدير الآن، بما فيها ما أُعيد إرساله بعد التعديل. لا تتأثر بالفترة الزمنية.',
    opens: { tab: 'submitted' },
  },
  {
    key: 'awaiting_updates', title: 'بانتظار تعديل الموظف', icon: 'history', period: false, sub: 'أُعيدت ولم تُرسل مجددًا',
    info: 'الطلبات المُعادة إلى الموظف التي لم تُرسل مرة أخرى بعد. لا تتأثر بالفترة الزمنية.',
    opens: { tab: 'returned' },
  },
  {
    key: 'review_hours', title: 'زمن المراجعة', icon: 'clock', period: true, sub: 'الوسيط حتى أول قرار',
    info: 'الوسيط (القيمة الوسطى) للمدة من أول إرسال حتى أول قرار — اعتماد أو إعادة للتعديل — للطلبات التي اتُّخذ أول قرار عليها خلال الفترة. يُستبعد الطلب الذي اعتمده صاحبه بنفسه.',
    opens: { tab: 'all', basis: 'decided' },
  },
];

const STATUS_LABELS = { submitted: 'بانتظار المراجعة', returned: 'بانتظار التعديل' };
const inTab = (row, tab) => tab === 'all' || row.status === tab;
// Which way is the good way for each card: more work sent and approved, less time waiting for a decision
const BETTER = { submitted: 1, approved: 1, review_hours: -1 };

/** How this period compares with the one of the same length before it. */
function Delta({ card, cards, before }) {
  if (!card.period || !before) return null;
  const change = compare(cards[card.key], before[card.key]);
  if (!change) return null;
  if (!change.direction) return <span className="fl-delta fl-delta--flat">بلا تغيّر عن الفترة السابقة</span>;
  const sign = change.direction > 0 ? '+' : '−';
  const size = change.percent === null ? Math.abs(change.change) : `${Math.abs(change.percent)}%`;
  const good = change.direction === BETTER[card.key];
  return (
    <span className={`fl-delta fl-delta--${good ? 'good' : 'bad'}`}
      title={`الفترة السابقة: ${formatDay(before.from)} — ${formatDay(before.to)}`}>
      <bdi dir="ltr" data-fl-num>{sign}{size}</bdi> عن الفترة السابقة
    </span>
  );
}

/** One of the five cards. A card with nothing to show still opens its (empty) list. */
function StatCard({ card, cards, before, onOpen }) {
  const isTime = card.key === 'review_hours';
  const value = cards[card.key];
  const shown = isTime ? (value === null ? 'لا توجد بيانات' : formatHours(value)) : value;
  return (
    <div className="fl-stat">
      <div className="fl-stat__head">
        <Icon name={card.icon} size={20} />
        <Badge tone={card.period ? 'neutral' : 'warning'}>{card.period ? 'خلال الفترة' : 'حاليًا'}</Badge>
      </div>
      <h3 className="fl-stat__title">
        {card.title}
        <span className="fl-stat__info" tabIndex={0} role="note" aria-label={card.info} title={card.info}>
          <Icon name="info" size={15} />
        </span>
      </h3>
      <p className={`fl-stat__value${isTime && value === null ? ' fl-stat__value--none' : ''}`}>{shown}</p>
      <Delta card={card} cards={cards} before={before} />
      <p className="fl-stat__sub">{card.sub}</p>
      <Button size="sm" variant="ghost" icon="arrow-end" onClick={() => onOpen(card)}>
        {isTime ? 'عرض التفاصيل' : 'عرض الطلبات'}
      </Button>
    </div>
  );
}

/** One line of «محتاج متابعة منك». */
function AttentionRow({ row, onOpen }) {
  return (
    <tr>
      <td className="fl-cell--id" data-label="الطلب">
        <bdi dir="ltr">#{row.id}</bdi>
        <span className="fl-cell__sub"><bdi>{row.customer_name || '—'}</bdi></span>
      </td>
      <td className="fl-cell--wrap" data-label="نوع النموذج">{row.form_label}</td>
      <td data-label="الموظف المسؤول"><bdi>{row.owner_name}</bdi></td>
      <td data-label="الحالة">
        <Badge tone={row.status === 'submitted' ? 'warning' : 'error'}>{STATUS_LABELS[row.status]}</Badge>
      </td>
      <td className="fl-cell--nowrap" data-label="مدة الانتظار">
        {waitedSince(row.waiting_since)}
        <span className="fl-cell__sub"><bdi dir="ltr">{formatDate(row.waiting_since)}</bdi></span>
      </td>
      <td className="fl-cell--wrap" data-label="سبب الإرجاع">
        {row.returned_reason ? <span className="fl-clamp" title={row.returned_reason}>{row.returned_reason}</span> : '—'}
      </td>
      <td className="fl-cell--actions">
        <Button size="sm" variant={row.can_review && row.status === 'submitted' ? 'primary' : 'secondary'}
          icon="eye" onClick={() => onOpen(row)}>
          {row.can_review && row.status === 'submitted' ? 'مراجعة الطلب' : 'عرض الطلب'}
        </Button>
      </td>
    </tr>
  );
}

export default function Dashboard({ onOpenRequest, onOpenList }) {
  const [params, setParams] = useSearchParams();
  const today = uaeToday();
  const [firstOfMonth, lastOfMonth] = rangeOf('month', today);
  const from = params.get('from') || firstOfMonth;
  const to = params.get('to') || lastOfMonth;
  const formType = params.get('form') || '';
  const employee = params.get('employee') || '';
  const tab = TABS.some((one) => one.value === params.get('tab')) ? params.get('tab') : 'all';
  const sort = SORTS.some((one) => one.value === params.get('sort')) ? params.get('sort') : 'oldest';

  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const invalid = periodError(from, to);

  // Only the filters that are set go in the URL, so a plain /dashboard stays plain
  const change = (values) => setParams((current) => {
    const next = new URLSearchParams(current);
    for (const [name, value] of Object.entries(values)) {
      if (value) next.set(name, value);
      else next.delete(name);
    }
    return next;
  }, { replace: true });

  const load = useCallback((quiet = false) => {
    if (!quiet) setLoading(true);
    return dashboardApi.overview({ from, to, form_type: formType, employee, sort })
      .then((answer) => { setData(answer); setError(''); })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [from, to, formType, employee, sort]);

  useEffect(() => { if (!invalid) load(); }, [load, invalid]);
  useEffect(() => {
    if (invalid) return undefined;
    const timer = setInterval(() => load(true), REFRESH_MS);
    return () => clearInterval(timer);
  }, [load, invalid]);

  const rows = useMemo(() => (data?.attention || []).filter((row) => inTab(row, tab)), [data, tab]);
  const preset = presetOf(from, to, today);
  const openList = (card) => onOpenList({
    ...card.opens, form: formType, employee,
    // A backlog card is about now: its list keeps the employee and the form, never the dates
    ...(card.period ? { from, to } : {}),
  });

  return (
    <div className="fl-stack">
      <PageHeader
        title="لوحة المتابعة" subtitle="حركة الطلبات، الأعمال المعلقة، وزمن أول مراجعة"
        actions={(
          <>
            {data && <span className="fl-small fl-muted">آخر تحديث: <bdi dir="ltr">{formatDate(data.refreshed_at)}</bdi></span>}
            <Button size="sm" icon="refresh" onClick={() => load()} disabled={Boolean(invalid)}>تحديث</Button>
          </>
        )}
      />

      <section className="fl-card fl-filterbar" aria-label="تصفية لوحة المتابعة">
        {/* The presets stay in sight on a phone; the rest open behind «الفلاتر», as everywhere else */}
        <Filters
          active={[formType, employee, preset ? '' : 'custom'].filter(Boolean).length}
          search={(
            <div className="fl-row" role="group" aria-label="الفترة الزمنية">
              {PRESETS.map((one) => {
                const [start, end] = rangeOf(one.value, today);
                return (
                  <Button key={one.value} size="sm" variant={preset === one.value ? 'primary' : 'secondary'}
                    aria-pressed={preset === one.value} onClick={() => change({ from: start, to: end })}>
                    {one.label}
                  </Button>
                );
              })}
            </div>
          )}
        >
          <Field label="من تاريخ" htmlFor="dash_from" error={invalid && from > to ? invalid : ''}>
            <TextInput id="dash_from" type="date" value={from} invalid={Boolean(invalid)}
              onChange={(e) => change({ from: e.target.value })} />
          </Field>
          <Field label="إلى تاريخ" htmlFor="dash_to">
            <TextInput id="dash_to" type="date" value={to} invalid={Boolean(invalid)}
              onChange={(e) => change({ to: e.target.value })} />
          </Field>
          <Field label="نوع النموذج" htmlFor="dash_form">
            <Select id="dash_form" value={formType} onChange={(e) => change({ form: e.target.value })}>
              <option value="">كل النماذج</option>
              {(data?.forms || []).map((form) => <option key={form.key} value={form.key}>{form.label}</option>)}
            </Select>
          </Field>
          <Field label="الموظف" htmlFor="dash_employee">
            <Select id="dash_employee" value={employee} onChange={(e) => change({ employee: e.target.value })}>
              <option value="">كل الموظفين</option>
              {(data?.employees || []).map((one) => <option key={one.id} value={one.id}>{one.name}</option>)}
            </Select>
          </Field>
        </Filters>
        <p className="fl-flush fl-small fl-muted">
          الفترة الزمنية تخص المرسلة والمعتمدة وزمن المراجعة • كارتا الانتظار يعرضان الوضع الحالي
        </p>
      </section>

      {invalid && <Alert tone="error">{invalid}</Alert>}
      {error && (
        <Alert tone="error" title="تعذر تحميل اللوحة" actions={<Button size="sm" onClick={() => load()}>إعادة المحاولة</Button>}>
          {error}
        </Alert>
      )}

      {!data && !error && !invalid && <Skeleton lines={5} />}
      {data && !invalid && (
        <>
          <div className={`fl-stats${loading ? ' fl-stats--loading' : ''}`}>
            {CARDS.map((card) => (
              <StatCard key={card.key} card={card} cards={data.cards} before={data.before} onOpen={openList} />
            ))}
          </div>

          <div className={`fl-charts${loading ? ' fl-stats--loading' : ''}`}>
            <TrendChart trend={data.trend} from={data.from} to={data.to} />
            <FormBars rows={data.by_form} onPick={(key) => change({ form: key === formType ? '' : key })} />
          </div>

          <section className="fl-card" aria-label="محتاج متابعة منك">
            <div className="fl-card__head">
              <div>
                <h2 className="fl-card__title">
                  محتاج متابعة منك <span className="fl-count" data-fl-num>{data.attention.length}</span>
                </h2>
                <p className="fl-flush fl-small fl-muted">
                  يعرض كل الطلبات المعلقة حاليًا، بما فيها ما قبل الفترة الزمنية المختارة.
                </p>
              </div>
              <Field label="الترتيب" htmlFor="dash_sort" className="fl-sortfield">
                <Select id="dash_sort" value={sort}
                  onChange={(event) => change({ sort: event.target.value === 'oldest' ? '' : event.target.value })}>
                  {SORTS.map((one) => <option key={one.value} value={one.value}>{one.label}</option>)}
                </Select>
              </Field>
            </div>
            <Tabs
              label="حالة الطلب" value={tab} onChange={(value) => change({ tab: value === 'all' ? '' : value })}
              tabs={TABS.map((one) => ({
                ...one, count: (data.attention || []).filter((row) => inTab(row, one.value)).length,
              }))}
            />
            <p className="fl-results">المراجعة: منذ آخر إرسال • التعديل: منذ الإرجاع</p>
            {!rows.length ? (
              <EmptyState icon="check-circle" title={tab === 'all' ? 'لا توجد طلبات تحتاج متابعة' : 'لا توجد طلبات في هذا التبويب'}>
                {tab === 'all' ? 'كل الطلبات المرسلة تمت مراجعتها.' : 'جرّب تبويبًا آخر أو غيّر الفلاتر.'}
              </EmptyState>
            ) : (
              <div className="fl-table-wrap">
                <div className="fl-table-scroll fl-table-scroll--bounded">
                  <table className="fl-table fl-table--sticky">
                    <thead>
                      <tr>
                        <th>الطلب</th><th>نوع النموذج</th><th>الموظف المسؤول</th><th>الحالة</th>
                        <th>مدة الانتظار</th><th>سبب الإرجاع</th><th>الإجراء</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => <AttentionRow key={row.id} row={row} onOpen={onOpenRequest} />)}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            <p className="fl-results">
              عرض {rows.length} من {data.attention.length} طلبًا تحتاج متابعة
              {data.attention.length >= 200 && ' (أول 200)'}
            </p>
          </section>
        </>
      )}
    </div>
  );
}
