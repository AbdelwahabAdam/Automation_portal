import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import * as reviewApi from '../../api/review.js';
import {
  Alert, Button, EmptyState, Field, Filters, PageHeader, SearchInput, Select, Skeleton, Tabs, TextInput, useWidth,
} from '../../ds/index.jsx';
import { matchesQuery } from '../../ds/match.js';
import { BASIS_LABELS, basisDate, inPeriod } from './queue.js';
import RequestList, { TABLE_MIN_WIDTH } from './RequestList.jsx';

const TABS = [
  { value: 'submitted', label: 'قيد المراجعة' },
  { value: 'returned', label: 'تحتاج تعديل' },
  { value: 'approved', label: 'المعتمدة' },
  // The employees' forms not sent yet, for the manager to follow; they can only be read
  { value: 'draft', label: 'المسودات' },
  // Everything sent; drafts have their own tab
  { value: 'all', label: 'الكل' },
];

// For sales managers: every request that has been sent, to approve or return with a reason, and
// the employees' drafts with a count per employee
const REFRESH_MS = 60 * 1000;
const inTab = (r, tab) => (tab === 'all' ? r.status !== 'draft' : r.status === tab);
// A draft has not been sent: it goes by when it was last saved
const dateOf = (r) => (r.status === 'draft' ? r.updated_at : r.submitted_at);

export default function Review({ user, sales, onOpen }) {
  const [requests, setRequests] = useState(null);
  const [error, setError] = useState('');
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [area, areaWidth] = useWidth();
  const tab = TABS.some((t) => t.value === params.get('tab')) ? params.get('tab') : 'submitted';
  // The filters live in the URL, so a card on لوحة المتابعة can open this screen on exactly the
  // requests it counted, and coming back here finds the screen as it was left.
  const employee = params.get('employee') || '';
  const formType = params.get('form') || '';
  const from = params.get('from') || '';
  const to = params.get('to') || '';
  // Which moment the dates are read on: when it was first sent, approved, first decided on —
  // or, without one, the screen's own date as always
  const basis = BASIS_LABELS[params.get('basis')] ? params.get('basis') : '';
  // Opened from لوحة المتابعة, which counts only the forms this user may decide on
  const scope = params.get('scope') === 'review' ? 'review' : '';
  const change = (values) => setParams((current) => {
    const next = new URLSearchParams(current);
    for (const [name, value] of Object.entries(values)) {
      if (value) next.set(name, value);
      else next.delete(name);
    }
    return next;
  }, { replace: true });
  const shownDate = (r) => (basis ? basisDate(r, basis) : dateOf(r));
  const dateLabel = basis ? BASIS_LABELS[basis] : (tab === 'draft' ? 'آخر حفظ' : 'تاريخ الإرسال');

  const load = useCallback(
    () => reviewApi.queue(scope).then(setRequests).catch((err) => setError(err.message)), [scope],
  );
  useEffect(() => { load(); }, [load]);
  // Drafts are saved, sent and deleted all day; the counts follow without reloading the page
  useEffect(() => {
    const timer = setInterval(load, REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);
  useEffect(() => setPage(1), [tab, query, employee, formType, from, to, basis, pageSize]);

  const filtered = useMemo(() => (requests || []).filter((r) => (
    inTab(r, tab)
      && (!employee || String(r.created_by_id) === employee)
      && (!formType || r.form_type === formType)
      && inPeriod(r, basis, from, to)
      && matchesQuery(query, [r.id, r.data.customer_name, r.data.phone, r.data.client_code].filter(Boolean).join(' '))
  )), [requests, tab, employee, formType, from, to, basis, query]);

  const header = <PageHeader title="مراجعة الطلبات" subtitle="راجع الطلبات المرسلة واعتمدها أو أعدها للموظف مع سبب التعديل" />;
  if (sales.error || error) return <div className="fl-stack">{header}<Alert tone="error">{sales.error || error}</Alert></div>;
  if (!requests || !sales.formTypes) return <div className="fl-stack" ref={area}>{header}<Skeleton lines={6} /></div>;
  const labels = Object.fromEntries(sales.formTypes.map((type) => [type.key, type.label]));
  const employees = [...new Map(requests.map((r) => [r.created_by_id, r.created_by_name])).entries()];
  const shown = filtered.slice((page - 1) * pageSize, page * pageSize);
  const action = (r) => {
    if (r.status === 'submitted') return <Button size="sm" variant="primary" icon="eye" onClick={() => onOpen(r)}>مراجعة الطلب</Button>;
    return <Button size="sm" icon="eye" onClick={() => onOpen(r)}>{r.status === 'draft' ? 'عرض المسودة' : 'عرض الطلب'}</Button>;
  };
  // Each employee with drafts, and how many, most first
  const draftCounts = [...requests.filter((r) => r.status === 'draft').reduce((counts, r) => {
    const [name, count] = counts.get(r.created_by_id) || [r.created_by_name, 0];
    return counts.set(r.created_by_id, [name, count + 1]);
  }, new Map()).entries()].sort((a, b) => b[1][1] - a[1][1] || a[1][0].localeCompare(b[1][0]));

  let list;
  if (!filtered.length) {
    list = (
      tab === 'draft' && !draftCounts.length ? (
        <EmptyState icon="check-circle" title="لا توجد مسودات">لا يوجد عند الموظفين نماذج محفوظة لم تُرسل بعد.</EmptyState>
      ) : (
        <EmptyState icon={tab === 'submitted' ? 'check-circle' : 'search'} title={tab === 'submitted' && !query ? 'لا توجد طلبات بانتظار المراجعة' : 'لا توجد طلبات مطابقة'}>
          {tab === 'submitted' && !query ? 'كل الطلبات المرسلة تمت مراجعتها.' : 'غيّر البحث أو الفلاتر أو التبويب.'}
        </EmptyState>
      )
    );
  } else {
    list = (
      <RequestList
        rows={shown} total={filtered.length} wide={areaWidth >= TABLE_MIN_WIDTH} labels={labels} actions={action}
        columns={['id', 'type', 'client', 'employee', 'date', ...(basis === 'decided' ? ['wait'] : []), 'status']}
        dateLabel={dateLabel} dateOf={shownDate}
        page={page} pageSize={pageSize} onPage={setPage} onPageSize={setPageSize}
      />
    );
  }

  return (
    <div className="fl-stack" ref={area}>
      {header}
      <Tabs
        label="حالة الطلب" value={tab}
        onChange={(value) => change({ tab: value === 'submitted' ? '' : value })}
        tabs={TABS.map((t) => ({ value: t.value, label: t.label, count: requests.filter((r) => inTab(r, t.value)).length }))}
      />
      {tab === 'draft' && draftCounts.length > 0 && (
        <section className="fl-draftcounts" aria-label="عدد المسودات لكل موظف">
          <span className="fl-small fl-muted">المسودات لكل موظف — اختر موظفًا لعرض مسوداته:</span>
          <div className="fl-row">
            {draftCounts.map(([id, [name, count]]) => (
              <Button
                key={id} size="sm" variant={employee === String(id) ? 'primary' : 'secondary'} aria-pressed={employee === String(id)}
                onClick={() => change({ employee: employee === String(id) ? '' : String(id) })}
              >
                <bdi>{name}</bdi> <span data-fl-num>({count})</span>
              </Button>
            ))}
          </div>
        </section>
      )}
      <Filters
        active={[employee, formType, from, to].filter(Boolean).length}
        search={(
          <Field label="بحث" htmlFor="review_search" hideLabel>
            <SearchInput id="review_search" value={query} onChange={setQuery} placeholder="ابحث برقم الطلب أو اسم العميل أو الهاتف أو كود العميل" />
          </Field>
        )}
      >
        <Field label="اسم الموظف" htmlFor="review_employee">
          <Select id="review_employee" value={employee} onChange={(e) => change({ employee: e.target.value })}>
            <option value="">كل الموظفين</option>
            {employees.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </Select>
        </Field>
        <Field label="نوع النموذج" htmlFor="review_type">
          <Select id="review_type" value={formType} onChange={(e) => change({ form: e.target.value })}>
            <option value="">كل النماذج</option>
            {/* A hidden form is offered only if there are requests made with it */}
            {sales.formTypes.filter((type) => !type.hidden || requests.some((r) => r.form_type === type.key))
              .map((type) => <option key={type.key} value={type.key}>{type.label}</option>)}
          </Select>
        </Field>
        <Field label={`${dateLabel} من`} htmlFor="review_from">
          <TextInput id="review_from" type="date" value={from} onChange={(e) => change({ from: e.target.value })} />
        </Field>
        <Field label={`${dateLabel} إلى`} htmlFor="review_to">
          <TextInput id="review_to" type="date" value={to} onChange={(e) => change({ to: e.target.value })} />
        </Field>
      </Filters>
      <p className="fl-results">النتائج: {filtered.length} من {requests.filter((r) => inTab(r, tab)).length}</p>
      {list}
    </div>
  );
}
