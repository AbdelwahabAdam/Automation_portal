import { Fragment, useEffect, useState } from 'react';
import * as auditApi from '../../api/audit.js';
import {
  Alert, Badge, Button, EmptyState, Field, Filters, PageHeader, Pager, SearchInput, Select, Skeleton, TextInput,
} from '../../ds/index.jsx';
import { formatDate } from '../../lib/format.js';

const NO_FILTERS = { user_id: '', action: '', entity_type: '', date_from: '', date_to: '', search: '' };
const FAILED = new Set(['auth.login_failed']);
const DELETES = new Set(['user.delete', 'role.delete', 'request.delete', 'attachment.delete', 'product.delete', 'package.delete']);

function queryOf(filters, extra = {}) {
  const filled = Object.entries({ ...filters, ...extra }).filter(([, value]) => value !== '');
  return new URLSearchParams(filled).toString();
}

function Changes({ entry, options }) {
  const keys = [...new Set([...Object.keys(entry.before || {}), ...Object.keys(entry.after || {})])];
  const show = (value) => {
    if (value === undefined || value === null || value === '') return '—';
    if (typeof value === 'boolean') return value ? 'نعم' : 'لا';
    if (Array.isArray(value)) return value.length ? value.map((v) => options.value_labels[v] || v).join('، ') : '—';
    return options.value_labels[value] || String(value);
  };
  return (
    <div className="fl-stack fl-stack--sm">
      {keys.length > 0 ? (
        <div className="fl-table-wrap">
          <table className="fl-table">
            <thead><tr><th>الحقل</th><th>قبل</th><th>بعد</th></tr></thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key}>
                  <td>{options.field_labels[key] || key}</td>
                  <td className="fl-cell--wrap"><bdi>{show(entry.before?.[key])}</bdi></td>
                  <td className="fl-cell--wrap"><bdi>{show(entry.after?.[key])}</bdi></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="fl-muted fl-small fl-flush">لا توجد قيم مسجلة لهذا الإجراء.</p>}
      <p className="fl-field__hint fl-flush">المتصفح: <bdi dir="ltr">{entry.user_agent || '—'}</bdi></p>
    </div>
  );
}

export default function AuditLog() {
  const [options, setOptions] = useState(null);
  const [filters, setFilters] = useState(NO_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [result, setResult] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    auditApi.options().then(setOptions).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    let stale = false;
    setError('');
    auditApi.page(queryOf(filters, { limit: pageSize, offset: (page - 1) * pageSize }))
      .then((loaded) => !stale && setResult(loaded))
      .catch((err) => !stale && setError(err.message));
    return () => { stale = true; };
  }, [filters, page, pageSize]);

  function setFilter(name, value) {
    setFilters((current) => ({ ...current, [name]: value }));
    setPage(1);
    setOpenId(null);
  }

  async function exportCsv() {
    setExporting(true);
    setError('');
    try {
      await auditApi.exportCsv(queryOf(filters));
    } catch (err) {
      setError(err.message);
    } finally {
      setExporting(false);
    }
  }

  const total = result?.total ?? 0;
  const header = (
    <PageHeader title="سجل النشاط" subtitle="كل دخول وتعديل وتحميل ملف، مع القيم قبل التعديل وبعده"
      actions={<Button icon="download" loading={exporting} disabled={!total} onClick={exportCsv}>تصدير إلى Excel</Button>} />
  );
  if (!options) return <div className="fl-stack">{header}{error ? <Alert tone="error">{error}</Alert> : <Skeleton lines={6} />}</div>;

  const filtered = Object.values(filters).some((value) => value !== '');
  const actionTone = (action) => (FAILED.has(action) || DELETES.has(action) ? 'error' : action.startsWith('auth.') ? 'neutral' : 'info');
  return (
    <div className="fl-stack">
      {header}
      <Filters
        active={[filters.user_id, filters.action, filters.entity_type, filters.date_from, filters.date_to].filter(Boolean).length}
        search={(
          <Field label="بحث" htmlFor="f_search" hideLabel>
            <SearchInput id="f_search" value={filters.search} onChange={(v) => setFilter('search', v)} placeholder="ابحث باسم المستخدم أو العميل أو رقم الطلب" />
          </Field>
        )}
      >
        <Field label="المستخدم" htmlFor="f_user">
          <Select id="f_user" value={filters.user_id} onChange={(e) => setFilter('user_id', e.target.value)}>
            <option value="">كل المستخدمين</option>
            {options.users.map((user) => (
              <option key={user.id} value={user.id}>{user.full_name ? `${user.full_name} (${user.username})` : user.username}</option>
            ))}
          </Select>
        </Field>
        <Field label="الإجراء" htmlFor="f_action">
          <Select id="f_action" value={filters.action} onChange={(e) => setFilter('action', e.target.value)}>
            <option value="">كل الإجراءات</option>
            {Object.entries(options.actions).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </Select>
        </Field>
        <Field label="نوع السجل" htmlFor="f_entity">
          <Select id="f_entity" value={filters.entity_type} onChange={(e) => setFilter('entity_type', e.target.value)}>
            <option value="">كل الأنواع</option>
            {Object.entries(options.entity_types).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </Select>
        </Field>
        <Field label="من تاريخ" htmlFor="f_from">
          <TextInput id="f_from" type="date" value={filters.date_from} onChange={(e) => setFilter('date_from', e.target.value)} />
        </Field>
        <Field label="إلى تاريخ" htmlFor="f_to">
          <TextInput id="f_to" type="date" value={filters.date_to} onChange={(e) => setFilter('date_to', e.target.value)} />
        </Field>
      </Filters>
      {error && <Alert tone="error">{error}</Alert>}
      {!result ? (
        <Skeleton lines={6} />
      ) : !total ? (
        <EmptyState icon="history" title={filtered ? 'لا توجد سجلات مطابقة' : 'لا توجد سجلات بعد'} />
      ) : (
        <div className="fl-table-wrap">
          <div className="fl-table-scroll">
            <table className="fl-table">
              <thead>
                <tr><th>الوقت</th><th>المستخدم</th><th>الإجراء</th><th>السجل</th><th>عنوان IP</th><th>التفاصيل</th></tr>
              </thead>
              <tbody>
                {result.items.map((entry) => (
                  <Fragment key={entry.id}>
                    <tr>
                      <td className="fl-cell--nowrap" data-fl-num><bdi dir="ltr">{formatDate(entry.at)}</bdi></td>
                      <td><bdi>{entry.username || '—'}</bdi></td>
                      <td><Badge tone={actionTone(entry.action)}>{options.actions[entry.action] || entry.action}</Badge></td>
                      <td className="fl-cell--wrap"><bdi>{entry.entity_label || '—'}</bdi></td>
                      <td className="fl-cell--nowrap"><bdi dir="ltr">{entry.ip}</bdi></td>
                      <td className="fl-cell--actions">
                        <Button size="sm" variant="tertiary" iconEnd={openId === entry.id ? 'chevron-up' : 'chevron-down'}
                          aria-expanded={openId === entry.id} onClick={() => setOpenId(openId === entry.id ? null : entry.id)}>
                          {openId === entry.id ? 'إخفاء' : 'عرض'}
                        </Button>
                      </td>
                    </tr>
                    {openId === entry.id && (
                      <tr className="fl-row--detail"><td colSpan={6}><Changes entry={entry} options={options} /></td></tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={page} pageSize={pageSize} total={total} onPage={setPage} onPageSize={(size) => { setPageSize(size); setPage(1); }} sizes={[20, 50, 100]} />
        </div>
      )}
    </div>
  );
}
