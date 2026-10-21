import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from './api.js';
import {
  Alert, Button, EmptyState, Field, Filters, PageHeader, SearchInput, Select, Skeleton, Tabs, TextInput, useToast, useWidth,
} from './ds/index.jsx';
import { localDay, matchesQuery } from './formsMeta.js';
import RequestList, { TABLE_MIN_WIDTH } from './RequestList.jsx';
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
  const toast = useToast();

  const load = () => api('/review/requests').then(setRequests).catch((err) => setError(err.message));
  useEffect(() => { load(); }, []);
  useEffect(() => setPage(1), [tab, query, employee, formType, from, to, pageSize]);

  const filtered = useMemo(() => (requests || []).filter((r) => {
    // The day it was sent as the manager sees it, not the UTC one
    const day = localDay(r.submitted_at);
    return (tab === 'all' || r.status === tab)
      && (!employee || String(r.created_by_id) === employee)
      && (!formType || r.form_type === formType)
      && (!from || day >= from) && (!to || day <= to)
      && matchesQuery(query, [r.id, r.data.customer_name, r.data.phone, r.data.client_code].filter(Boolean).join(' '));
  }), [requests, tab, employee, formType, from, to, query]);

  const header = <PageHeader title="مراجعة الطلبات" subtitle="راجع الطلبات المرسلة واعتمدها أو أعدها للموظف مع سبب التعديل" />;
  if (sales.error || error) return <div className="fl-stack">{header}<Alert tone="error">{sales.error || error}</Alert></div>;
  if (!requests || !sales.formTypes) return <div className="fl-stack" ref={area}>{header}<Skeleton lines={6} /></div>;
  if (viewing) {
    return (
      <RequestView
        requestId={viewing.id} ownerName={viewing.created_by_name} formTypes={sales.formTypes}
        onBack={() => setViewing(null)}
        review={{
          own: () => viewing.created_by_id === user.id && !user.is_admin,
          onDone: (message) => { toast(message); setViewing(null); load(); },
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

  let list;
  if (!filtered.length) {
    list = (
      <EmptyState icon={tab === 'submitted' ? 'check-circle' : 'search'} title={tab === 'submitted' && !query ? 'لا توجد طلبات بانتظار المراجعة' : 'لا توجد طلبات مطابقة'}>
        {tab === 'submitted' && !query ? 'كل الطلبات المرسلة تمت مراجعتها.' : 'غيّر البحث أو الفلاتر أو التبويب.'}
      </EmptyState>
    );
  } else {
    list = (
      <RequestList
        rows={shown} total={filtered.length} wide={areaWidth >= TABLE_MIN_WIDTH} labels={labels} actions={action}
        columns={['id', 'type', 'client', 'employee', 'date', 'status']} dateLabel="تاريخ الإرسال" dateOf={(r) => r.submitted_at}
        page={page} pageSize={pageSize} onPage={setPage} onPageSize={setPageSize}
      />
    );
  }

  return (
    <div className="fl-stack" ref={area}>
      {header}
      <Tabs
        label="حالة الطلب" value={tab}
        onChange={(value) => setParams(value === 'submitted' ? {} : { tab: value }, { replace: true })}
        tabs={TABS.map((t) => ({ value: t.value, label: t.label, count: t.value === 'all' ? requests.length : requests.filter((r) => r.status === t.value).length }))}
      />
      <Filters
        active={[employee, formType, from, to].filter(Boolean).length}
        search={(
          <Field label="بحث" htmlFor="review_search" hideLabel>
            <SearchInput id="review_search" value={query} onChange={setQuery} placeholder="ابحث برقم الطلب أو اسم العميل أو الهاتف أو كود العميل" />
          </Field>
        )}
      >
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
      </Filters>
      <p className="fl-results">النتائج: {filtered.length} من {tab === 'all' ? requests.length : requests.filter((r) => r.status === tab).length}</p>
      {list}
    </div>
  );
}
