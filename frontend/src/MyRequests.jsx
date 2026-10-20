import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from './api.js';
import {
  Alert, Button, EmptyState, Field, Loading, PageHeader, Pager, SearchInput, Select, StatusBadge, Tabs, useWidth,
} from './ds/index.jsx';
import { formatDate, matchesQuery } from './formsMeta.js';

export { formatDate };

// Table on a wide area, cards on a narrow one (same data, same actions)
export const TABLE_MIN_WIDTH = 760;

const TABS = [
  { value: 'all', label: 'الكل', test: () => true },
  { value: 'draft', label: 'المسودات', test: (r) => r.status === 'draft' },
  { value: 'returned', label: 'تحتاج تعديل', test: (r) => r.status === 'returned' },
  { value: 'submitted', label: 'قيد المراجعة', test: (r) => r.status === 'submitted' },
  { value: 'approved', label: 'المعتمدة', test: (r) => r.status === 'approved' },
];

const searchText = (r) => [r.id, r.data.customer_name, r.data.phone, r.data.client_code].filter(Boolean).join(' ');

export default function MyRequests({ formTypes, onNew, onEdit, onView }) {
  const [requests, setRequests] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState('');
  const [formType, setFormType] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [area, areaWidth] = useWidth();
  const wide = areaWidth >= TABLE_MIN_WIDTH;
  const tab = TABS.some((t) => t.value === params.get('tab')) ? params.get('tab') : 'all';
  const labels = Object.fromEntries(formTypes.map((type) => [type.key, type.label]));

  useEffect(() => {
    api('/requests/mine').then(setRequests).catch((err) => setError(err.message));
  }, []);
  useEffect(() => setPage(1), [tab, query, formType, pageSize]);

  const filtered = useMemo(() => (requests || []).filter(
    (r) => TABS.find((t) => t.value === tab).test(r) && (!formType || r.form_type === formType) && matchesQuery(query, searchText(r)),
  ), [requests, tab, formType, query]);

  async function remove(request) {
    if (!window.confirm(`حذف المسودة رقم ${request.id}؟ لا يمكن التراجع.`)) return;
    setError('');
    try {
      await api(`/requests/${request.id}`, { method: 'DELETE' });
      setRequests((current) => current.filter((r) => r.id !== request.id));
      setNotice(`تم حذف المسودة رقم ${request.id}.`);
    } catch (err) {
      setError(err.message);
    }
  }

  const header = (
    <PageHeader title="طلباتي" subtitle="تابع طلباتك واستكمل المسودات والتعديلات المطلوبة"
      actions={<Button variant="primary" icon="plus" onClick={onNew}>طلب جديد</Button>} />
  );
  if (!requests) return <div className="fl-stack" ref={area}>{header}{error ? <Alert tone="error">{error}</Alert> : <Loading />}</div>;

  const shown = filtered.slice((page - 1) * pageSize, page * pageSize);
  const updated = (r) => formatDate(['draft', 'returned'].includes(r.status) ? r.updated_at : r.reviewed_at || r.submitted_at);
  const actions = (r) => {
    if (r.status === 'draft') {
      return (
        <>
          <Button size="sm" variant="primary" icon="edit" onClick={() => onEdit(r)}>استكمال</Button>
          <Button size="sm" variant="ghost" icon="trash" iconOnly label={`حذف المسودة ${r.id}`} onClick={() => remove(r)} />
        </>
      );
    }
    if (r.status === 'returned') return <Button size="sm" variant="primary" icon="edit" onClick={() => onEdit(r)}>تعديل الطلب</Button>;
    return <Button size="sm" icon="eye" onClick={() => onView(r)}>عرض الطلب</Button>;
  };
  // Why a returned request came back, under its row
  const note = (r) => r.status === 'returned' && r.returned_reason && <span className="fl-rownote">سبب الإعادة: {r.returned_reason}</span>;

  let list;
  if (!requests.length) {
    list = (
      <EmptyState title="لا توجد طلبات بعد" action={<Button icon="grid" onClick={onNew}>عرض النماذج</Button>}>
        اختر نموذجًا وابدأ أول طلب.
      </EmptyState>
    );
  } else if (!filtered.length) {
    list = <EmptyState icon="search" title="لا توجد طلبات مطابقة">غيّر البحث أو نوع النموذج أو التبويب.</EmptyState>;
  } else if (wide) {
    list = (
      <div className="fl-table-wrap">
        <div className="fl-table-scroll">
          <table className="fl-table">
            <thead>
              <tr><th>رقم الطلب</th><th>نوع النموذج</th><th>العميل</th><th>الحالة</th><th>آخر تحديث</th><th>الإجراء</th></tr>
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
                  <td><StatusBadge status={r.status} /></td>
                  <td className="fl-cell--nowrap" data-fl-num><bdi dir="ltr">{updated(r)}</bdi></td>
                  <td className="fl-cell--actions">{actions(r)}</td>
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
                <dt>آخر تحديث</dt><dd><bdi dir="ltr">{updated(r)}</bdi></dd>
              </dl>
              {note(r)}
              <div className="fl-row">{actions(r)}</div>
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
      <Tabs
        label="حالة الطلب"
        value={tab}
        onChange={(value) => setParams(value === 'all' ? {} : { tab: value }, { replace: true })}
        tabs={TABS.map((t) => ({ value: t.value, label: t.label, count: requests.filter(t.test).length }))}
      />
      <div className="fl-filters fl-filters--search">
        <Field label="بحث" htmlFor="my_search" hideLabel>
          <SearchInput id="my_search" value={query} onChange={setQuery} placeholder="ابحث برقم الطلب أو اسم العميل أو الهاتف أو كود العميل" />
        </Field>
        <Field label="نوع النموذج" htmlFor="my_form">
          <Select id="my_form" value={formType} onChange={(e) => setFormType(e.target.value)}>
            <option value="">كل النماذج</option>
            {/* A hidden form is offered only if there are requests made with it */}
            {formTypes.filter((type) => !type.hidden || (requests || []).some((r) => r.form_type === type.key))
              .map((type) => <option key={type.key} value={type.key}>{type.label}</option>)}
          </Select>
        </Field>
      </div>
      {notice && <Alert tone="success" onDismiss={() => setNotice('')}>{notice}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}
      {list}
    </div>
  );
}
