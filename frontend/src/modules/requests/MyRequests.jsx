import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from './api.js';
import {
  Alert, Button, EmptyState, Field, Filters, PageHeader, SearchInput, Select, Skeleton, Tabs, useConfirm, useToast, useWidth,
} from './ds/index.jsx';
import { matchesQuery } from './formsMeta.js';
import RequestList, { TABLE_MIN_WIDTH } from './RequestList.jsx';

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
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState('');
  const [formType, setFormType] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [area, areaWidth] = useWidth();
  const wide = areaWidth >= TABLE_MIN_WIDTH;
  const tab = TABS.some((t) => t.value === params.get('tab')) ? params.get('tab') : 'all';
  const labels = Object.fromEntries(formTypes.map((type) => [type.key, type.label]));
  const [confirmDialog, confirm] = useConfirm();
  const toast = useToast();

  useEffect(() => {
    api('/requests/mine').then(setRequests).catch((err) => setError(err.message));
  }, []);
  useEffect(() => setPage(1), [tab, query, formType, pageSize]);

  const filtered = useMemo(() => (requests || []).filter(
    (r) => TABS.find((t) => t.value === tab).test(r) && (!formType || r.form_type === formType) && matchesQuery(query, searchText(r)),
  ), [requests, tab, formType, query]);

  async function remove(request) {
    const yes = await confirm({
      title: `حذف المسودة رقم ${request.id}؟`, body: 'تُحذف المسودة ومرفقاتها، ولا يمكن التراجع.', confirmLabel: 'حذف المسودة', tone: 'danger',
    });
    if (!yes) return;
    setError('');
    try {
      await api(`/requests/${request.id}`, { method: 'DELETE' });
      setRequests((current) => current.filter((r) => r.id !== request.id));
      toast(`تم حذف المسودة رقم ${request.id}`);
    } catch (err) {
      setError(err.message);
    }
  }

  const header = (
    <PageHeader title="طلباتي" subtitle="تابع طلباتك واستكمل المسودات والتعديلات المطلوبة"
      actions={<Button variant="primary" icon="plus" onClick={onNew}>طلب جديد</Button>} />
  );
  if (!requests) return <div className="fl-stack" ref={area}>{header}{error ? <Alert tone="error">{error}</Alert> : <Skeleton lines={6} />}</div>;

  const shown = filtered.slice((page - 1) * pageSize, page * pageSize);
  // A request still with its owner was last changed by them; a sent one, when it was sent or decided
  const updatedAt = (r) => (['draft', 'returned'].includes(r.status) ? r.updated_at : r.reviewed_at || r.submitted_at);
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
  let list;
  if (!requests.length) {
    list = (
      <EmptyState title="لا توجد طلبات بعد" action={<Button icon="grid" onClick={onNew}>عرض النماذج</Button>}>
        اختر نموذجًا وابدأ أول طلب.
      </EmptyState>
    );
  } else if (!filtered.length) {
    list = <EmptyState icon="search" title="لا توجد طلبات مطابقة">غيّر البحث أو نوع النموذج أو التبويب.</EmptyState>;
  } else {
    list = (
      <RequestList
        rows={shown} total={filtered.length} wide={wide} labels={labels} actions={actions}
        columns={['id', 'type', 'client', 'status', 'date']} dateLabel="آخر تحديث" dateOf={updatedAt}
        page={page} pageSize={pageSize} onPage={setPage} onPageSize={setPageSize}
      />
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
      {error && <Alert tone="error">{error}</Alert>}
      {list}
      {confirmDialog}
    </div>
  );
}
