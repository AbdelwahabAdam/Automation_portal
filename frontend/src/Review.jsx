import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from './api.js';
import {
  Alert, Button, EmptyState, Field, Loading, PageHeader, Pager, SearchInput, Select, StatusBadge, Tabs, TextInput, useWidth,
} from './ds/index.jsx';
import { formatDate, matchesQuery } from './formsMeta.js';
import { TABLE_MIN_WIDTH } from './MyRequests.jsx';
import RequestView from './RequestView.jsx';

const TABS = [
  { value: 'submitted', label: 'قيد المراجعة' },
  { value: 'returned', label: 'تحتاج تعديل' },
  { value: 'approved', label: 'المعتمدة' },
  { value: 'all', label: 'الكل' },
];

// For sales managers: every request that has been sent, to approve or return with a reason
export default function Review({ user, sales }) {
  const [requests, setRequests] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState('');
  const [employee, setEmployee] = useState('');
  const [formType, setFormType] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [viewing, setViewing] = useState(null);
  const [area, areaWidth] = useWidth();
  const tab = TABS.some((t) => t.value === params.get('tab')) ? params.get('tab') : 'submitted';

  const load = () => api('/review/requests').then(setRequests).catch((err) => setError(err.message));
  useEffect(() => { load(); }, []);
  useEffect(() => setPage(1), [tab, query, employee, formType, from, to, pageSize]);

  const filtered = useMemo(() => (requests || []).filter((r) => {
    const day = (r.submitted_at || '').slice(0, 10);
    return (tab === 'all' || r.status === tab)
      && (!employee || String(r.created_by_id) === employee)
      && (!formType || r.form_type === formType)
      && (!from || day >= from) && (!to || day <= to)
      && matchesQuery(query, [r.id, r.data.customer_name, r.data.phone, r.data.client_code].filter(Boolean).join(' '));
  }), [requests, tab, employee, formType, from, to, query]);

  const header = <PageHeader title="مراجعة الطلبات" subtitle="راجع الطلبات المرسلة واعتمدها أو أعدها للموظف مع سبب التعديل" />;
  if (sales.error || error) return <div className="fl-stack">{header}<Alert tone="error">{sales.error || error}</Alert></div>;
  if (!requests || !sales.formTypes) return <div className="fl-stack" ref={area}>{header}<Loading /></div>;
  if (viewing) {
    return (
      <RequestView
        requestId={viewing.id} ownerName={viewing.created_by_name} formTypes={sales.formTypes}
        onBack={() => setViewing(null)}
        review={{
          own: () => viewing.created_by_id === user.id && !user.is_admin,
          onDone: (message) => { setNotice(message); setViewing(null); load(); },
        }}
      />
    );
  }

  const labels = Object.fromEntries(sales.formTypes.map((type) => [type.key, type.label]));
  const employees = [...new Map(requests.map((r) => [r.created_by_id, r.created_by_name])).entries()];
  const shown = filtered.slice((page - 1) * pageSize, page * pageSize);
  const action = (r) => (r.status === 'submitted'
    ? <Button size="sm" variant="primary" icon="eye" onClick={() => setViewing(r)}>مراجعة الطلب</Button>
    : <Button size="sm" icon="eye" onClick={() => setViewing(r)}>عرض الطلب</Button>);
  const note = (r) => r.status === 'returned' && r.returned_reason && <span className="fl-rownote">سبب الإعادة: {r.returned_reason}</span>;

  let list;
  if (!filtered.length) {
    list = (
      <EmptyState icon={tab === 'submitted' ? 'check-circle' : 'search'} title={tab === 'submitted' && !query ? 'لا توجد طلبات بانتظار المراجعة' : 'لا توجد طلبات مطابقة'}>
        {tab === 'submitted' && !query ? 'كل الطلبات المرسلة تمت مراجعتها.' : 'غيّر البحث أو الفلاتر أو التبويب.'}
      </EmptyState>
    );
  } else if (areaWidth >= TABLE_MIN_WIDTH) {
    list = (
      <div className="fl-table-wrap">
        <div className="fl-table-scroll">
          <table className="fl-table">
            <thead>
              <tr><th>رقم الطلب</th><th>نوع النموذج</th><th>العميل</th><th>الموظف</th><th>تاريخ الإرسال</th><th>الحالة</th><th>الإجراء</th></tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.id}>
                  <td className="fl-cell--id" data-fl-num>{r.id}</td>
                  <td className="fl-cell--wrap">{labels[r.form_type] || r.form_type}</td>
                  <td className="fl-cell--wrap">
                    <bdi>{r.data.customer_name || '—'}</bdi>
                    {r.data.phone && <span className="fl-cell__sub"><bdi dir="ltr">{r.data.phone}</bdi></span>}
                    {note(r)}
                  </td>
                  <td><bdi>{r.created_by_name}</bdi></td>
                  <td className="fl-cell--nowrap" data-fl-num><bdi dir="ltr">{formatDate(r.submitted_at)}</bdi></td>
                  <td><StatusBadge status={r.status} /></td>
                  <td className="fl-cell--actions">{action(r)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pager page={page} pageSize={pageSize} total={filtered.length} onPage={setPage} onPageSize={setPageSize} />
      </div>
    );
  } else {
    list = (
      <>
        <ul className="fl-cards" role="list">
          {shown.map((r) => (
            <li key={r.id} className="fl-rowcard">
              <div className="fl-rowcard__head">
                <span className="fl-rowcard__title">{labels[r.form_type] || r.form_type}</span>
                <StatusBadge status={r.status} />
              </div>
              <dl>
                <dt>رقم الطلب</dt><dd data-fl-num>{r.id}</dd>
                <dt>العميل</dt><dd><bdi>{r.data.customer_name || '—'}</bdi></dd>
                <dt>الموظف</dt><dd><bdi>{r.created_by_name}</bdi></dd>
                <dt>تاريخ الإرسال</dt><dd><bdi dir="ltr">{formatDate(r.submitted_at)}</bdi></dd>
              </dl>
              {note(r)}
              {action(r)}
            </li>
          ))}
        </ul>
        <div className="fl-table-wrap"><Pager page={page} pageSize={pageSize} total={filtered.length} onPage={setPage} /></div>
      </>
    );
  }

  return (
    <div className="fl-stack" ref={area}>
      {header}
      {notice && <Alert tone="success" onDismiss={() => setNotice('')}>{notice}</Alert>}
      <Tabs
        label="حالة الطلب" value={tab}
        onChange={(value) => setParams(value === 'submitted' ? {} : { tab: value }, { replace: true })}
        tabs={TABS.map((t) => ({ value: t.value, label: t.label, count: t.value === 'all' ? requests.length : requests.filter((r) => r.status === t.value).length }))}
      />
      <div className="fl-filters">
        <div className="fl-filters__search">
          <Field label="بحث" htmlFor="review_search" hideLabel>
            <SearchInput id="review_search" value={query} onChange={setQuery} placeholder="ابحث برقم الطلب أو اسم العميل أو الهاتف أو كود العميل" />
          </Field>
        </div>
        <Field label="اسم الموظف" htmlFor="review_employee">
          <Select id="review_employee" value={employee} onChange={(e) => setEmployee(e.target.value)}>
            <option value="">كل الموظفين</option>
            {employees.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </Select>
        </Field>
        <Field label="نوع النموذج" htmlFor="review_type">
          <Select id="review_type" value={formType} onChange={(e) => setFormType(e.target.value)}>
            <option value="">كل النماذج</option>
            {/* A hidden form is offered only if there are requests made with it */}
            {sales.formTypes.filter((type) => !type.hidden || requests.some((r) => r.form_type === type.key))
              .map((type) => <option key={type.key} value={type.key}>{type.label}</option>)}
          </Select>
        </Field>
        <Field label="تاريخ الإرسال من" htmlFor="review_from">
          <TextInput id="review_from" type="date" dir="ltr" value={from} onChange={(e) => setFrom(e.target.value)} />
        </Field>
        <Field label="تاريخ الإرسال إلى" htmlFor="review_to">
          <TextInput id="review_to" type="date" dir="ltr" value={to} onChange={(e) => setTo(e.target.value)} />
        </Field>
      </div>
      <p className="fl-results">النتائج: {filtered.length} من {tab === 'all' ? requests.length : requests.filter((r) => r.status === tab).length}</p>
      {list}
    </div>
  );
}
