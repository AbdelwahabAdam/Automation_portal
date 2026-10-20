import { useEffect, useState } from 'react';
import { api } from '../api.js';
import {
  Alert, Badge, Button, Choice, Drawer, EmptyState, Field, Loading, PageHeader, SearchInput, TextInput,
} from '../ds/index.jsx';
import { matchesQuery } from '../formsMeta.js';

function RoleDrawer({ role, departments, onSaved, onDeleted, onClose }) {
  const [name, setName] = useState(role?.name || '');
  const [pages, setPages] = useState(role?.pages || []);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');

  async function run(kind, action) {
    setBusy(kind);
    setError('');
    try {
      await action();
    } catch (err) {
      setError(err.message);
      setBusy('');
    }
  }

  const submit = (e) => {
    e?.preventDefault();
    run('save', async () => {
      const body = { name, pages };
      onSaved(role ? await api(`/admin/roles/${role.id}`, { method: 'PUT', body }) : await api('/admin/roles', { method: 'POST', body }));
    });
  };

  const remove = () => {
    if (!window.confirm(`حذف الدور «${role.name}»؟`)) return;
    run('delete', async () => {
      await api(`/admin/roles/${role.id}`, { method: 'DELETE' });
      onDeleted(role);
    });
  };

  // Each department's pages are one group of checkboxes; the role keeps the union
  const setDepartmentPages = (department, chosen) => {
    const keys = new Set(department.pages.map((page) => page.key));
    setPages((current) => [...current.filter((key) => !keys.has(key)), ...chosen]);
  };

  return (
    <Drawer
      title={role ? 'تعديل دور' : 'إضافة دور'}
      subtitle="الدور قائمة صفحات؛ من يفتح الصفحة يستطيع كل ما فيها. صفحات الإدارة لمدير النظام فقط."
      onClose={onClose}
      footer={(
        <>
          <Button variant="primary" loading={busy === 'save'} disabled={Boolean(busy)} onClick={submit}>حفظ</Button>
          <Button onClick={onClose}>إلغاء</Button>
          {role && (
            <span className="fl-push">
              <Button size="sm" variant="destructive-secondary" icon="trash" loading={busy === 'delete'} disabled={role.user_count > 0}
                title={role.user_count > 0 ? 'الدور مُسند لمستخدمين' : undefined} onClick={remove}>حذف الدور</Button>
            </span>
          )}
        </>
      )}
    >
      <form className="fl-stack fl-stack--sm" onSubmit={submit} noValidate>
        {error && <Alert tone="error">{error}</Alert>}
        <Field label="اسم الدور" htmlFor="role_name" required>
          <TextInput id="role_name" value={name} onChange={(e) => setName(e.target.value)} maxLength={60} />
        </Field>
        {departments.map((department) => (
          <Field key={department.key} label={department.label}>
            <Choice
              name={`pages_${department.key}`} multiple
              options={department.pages.map((page) => ({ value: page.key, label: page.label }))}
              value={pages.filter((key) => department.pages.some((page) => page.key === key))}
              onChange={(chosen) => setDepartmentPages(department, chosen)}
            />
          </Field>
        ))}
        {role?.user_count > 0 && <p className="fl-field__hint">لا يمكن حذف دور مُسند لمستخدمين؛ أزله عنهم أولًا.</p>}
      </form>
    </Drawer>
  );
}

export default function Permissions() {
  const [roles, setRoles] = useState(null);
  const [departments, setDepartments] = useState([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [query, setQuery] = useState('');
  // null | { role } (role undefined for a new one)
  const [panel, setPanel] = useState(null);

  useEffect(() => {
    Promise.all([api('/admin/roles'), api('/admin/pages')])
      .then(([loadedRoles, loadedDepartments]) => {
        setRoles(loadedRoles);
        setDepartments(loadedDepartments);
      })
      .catch((err) => setError(err.message));
  }, []);

  const pageLabels = Object.fromEntries(
    departments.flatMap((department) => department.pages.map((page) => [page.key, `${department.label} / ${page.label}`])),
  );

  function open(next) {
    setNotice('');
    setError('');
    setPanel(next);
  }

  function saved(savedRole) {
    setRoles((current) => (current.some((r) => r.id === savedRole.id)
      ? current.map((r) => (r.id === savedRole.id ? savedRole : r))
      : [...current, savedRole]));
    setNotice(`تم حفظ الدور ${savedRole.name}.`);
    setPanel(null);
  }

  function deleted(role) {
    setRoles((current) => current.filter((r) => r.id !== role.id));
    setNotice(`تم حذف الدور ${role.name}.`);
    setPanel(null);
  }

  const header = (
    <PageHeader title="الأدوار والصلاحيات" subtitle="حدد الصفحات التي يفتحها كل دور، ثم أسند الأدوار للمستخدمين"
      actions={<Button variant="primary" icon="plus" onClick={() => open({})}>إضافة دور</Button>} />
  );
  if (!roles) return <div className="fl-stack">{header}{error ? <Alert tone="error">{error}</Alert> : <Loading />}</div>;

  const shown = roles.filter((role) => matchesQuery(query, role.name, ...role.pages.map((key) => pageLabels[key] || '')));
  return (
    <div className="fl-stack">
      {header}
      {notice && <Alert tone="success" onDismiss={() => setNotice('')}>{notice}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}
      <SearchInput value={query} onChange={setQuery} placeholder="ابحث باسم الدور أو الصفحة" />
      <p className="fl-results">النتائج: {shown.length} من {roles.length}</p>
      {!shown.length ? (
        <EmptyState icon="shield" title={roles.length ? 'لا يوجد دور مطابق' : 'لا توجد أدوار بعد'}
          action={!roles.length && <Button icon="plus" onClick={() => open({})}>إضافة دور</Button>} />
      ) : (
        <div className="fl-table-wrap">
          <div className="fl-table-scroll">
            <table className="fl-table">
              <thead><tr><th>اسم الدور</th><th>الصفحات</th><th>عدد المستخدمين</th><th>الإجراء</th></tr></thead>
              <tbody>
                {shown.map((role) => (
                  <tr key={role.id}>
                    <td className="fl-cell--id"><bdi>{role.name}</bdi></td>
                    <td className="fl-cell--wrap">
                      <div className="fl-badges">
                        {role.pages.length
                          ? role.pages.map((key) => <Badge key={key} tone="brand">{pageLabels[key] || key}</Badge>)
                          : <span className="fl-muted">بدون صفحات</span>}
                      </div>
                    </td>
                    <td data-fl-num>{role.user_count}</td>
                    <td className="fl-cell--actions"><Button size="sm" icon="edit" onClick={() => open({ role })}>تعديل</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {panel && (
        <RoleDrawer key={panel.role?.id ?? 'new'} role={panel.role} departments={departments} onSaved={saved} onDeleted={deleted} onClose={() => setPanel(null)} />
      )}
    </div>
  );
}
