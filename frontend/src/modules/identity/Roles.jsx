import { useEffect, useMemo, useState } from 'react';
import * as identityApi from '../../api/identity.js';
import {
  Alert, Badge, Button, Checkbox, Choice, Drawer, EmptyState, Field, PageHeader, SearchInput, Select, Skeleton,
  Tabs, TextInput, useConfirm, useToast,
} from '../../ds/index.jsx';
import { matchesQuery } from '../../ds/match.js';
import { useAction } from '../../lib/hooks.js';

// Two tabs over the same data: one role at a time, or one form at a time.
const TABS = [
  { value: 'roles', label: 'الأدوار' },
  { value: 'forms', label: 'النماذج' },
];
const DOES = ['submit', 'view', 'review'];

/** Every permission a role holds, as readable labels, for the search box and the badges. */
function labelsOf(offered) {
  const labels = {};
  for (const form of offered.forms || []) {
    for (const does of DOES) {
      if (form.keys[does]) labels[form.keys[does]] = `${offered.what[does]} — ${form.label}`;
    }
  }
  for (const page of offered.admin_pages || []) labels[page.key] = page.label;
  return labels;
}

/** One role: a row per form with three boxes, then the admin pages. */
function RoleDrawer({ role, offered, onSaved, onDeleted, onClose }) {
  const [name, setName] = useState(role?.name || '');
  const [held, setHeld] = useState(() => new Set(role?.permissions || []));
  const { error, busy, run } = useAction();
  const [confirmDialog, confirm] = useConfirm();

  const toggle = (key, on) => setHeld((current) => {
    const next = new Set(current);
    if (on) next.add(key); else next.delete(key);
    return next;
  });

  const submit = (e) => {
    e?.preventDefault();
    run('save', async () => {
      const body = { name, permissions: [...held] };
      onSaved(role ? await identityApi.updateRole(role.id, body) : await identityApi.createRole(body));
    });
  };

  const remove = async () => {
    if (!(await confirm({ title: `حذف الدور «${role.name}»؟`, body: 'يُحذف الدور نهائيًا.', confirmLabel: 'حذف الدور', tone: 'danger' }))) return;
    run('delete', async () => {
      await identityApi.deleteRole(role.id);
      onDeleted(role);
    });
  };

  return (
    <>
    {confirmDialog}
    <Drawer
      title={role ? 'تعديل دور' : 'إضافة دور'}
      subtitle="لكل نموذج ثلاث صلاحيات: تعبئة النموذج، عرض طلبات الجميع، ومراجعتها. المستخدمون والأدوار لمدير النظام فقط."
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
        <Field label="النماذج">
          <div className="fl-table-wrap fl-stacked fl-stacked--checks">
            <div className="fl-table-scroll">
              <table className="fl-table">
                <thead>
                  <tr>
                    <th>النموذج</th>
                    {DOES.map((does) => <th key={does}>{offered.what[does]}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {(offered.forms || []).map((form) => (
                    <tr key={form.key}>
                      <td className="fl-cell--id"><bdi>{form.label}</bdi></td>
                      {DOES.map((does) => (
                        <td key={does} data-label={offered.what[does]}>
                          <Checkbox checked={held.has(form.keys[does])}
                            onChange={(on) => toggle(form.keys[does], on)} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </Field>
        <Field label="صفحات الإدارة">
          <Choice
            name="admin_pages" multiple
            options={(offered.admin_pages || []).map((page) => ({ value: page.key, label: page.label }))}
            value={(offered.admin_pages || []).map((p) => p.key).filter((key) => held.has(key))}
            onChange={(chosen) => setHeld((current) => {
              const admin = new Set((offered.admin_pages || []).map((p) => p.key));
              return new Set([...[...current].filter((key) => !admin.has(key)), ...chosen]);
            })}
          />
        </Field>
        {role?.user_count > 0 && <p className="fl-field__hint">لا يمكن حذف دور مُسند لمستخدمين؛ أزله عنهم أولًا.</p>}
      </form>
    </Drawer>
    </>
  );
}

/** One form at a time: which roles can fill it, see it and review it. */
function FormAccess({ offered, roles, onSaved }) {
  const [formKey, setFormKey] = useState(offered.forms?.[0]?.key || '');
  const [query, setQuery] = useState('');
  const { error, busy, run } = useAction();
  const toast = useToast();

  const form = (offered.forms || []).find((f) => f.key === formKey);
  const shown = (offered.forms || []).filter((f) => matchesQuery(query, f.label, f.key));

  const grant = (role, does, on) => run(`${role.id}:${does}`, async () => {
    const key = form.keys[does];
    const permissions = on
      ? [...new Set([...role.permissions, key])]
      : role.permissions.filter((held) => held !== key);
    onSaved(await identityApi.updateRole(role.id, { name: role.name, permissions }));
    toast(`تم تحديث «${role.name}»`);
  });

  if (!form) return <EmptyState icon="file" title="لا توجد نماذج" />;
  return (
    <div className="fl-stack fl-stack--sm">
      {error && <Alert tone="error">{error}</Alert>}
      <SearchInput value={query} onChange={setQuery} placeholder="ابحث عن نموذج" />
      <Field label="النموذج" htmlFor="form_key">
        <Select id="form_key" value={formKey} onChange={(e) => setFormKey(e.target.value)}>
          {shown.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
        </Select>
      </Field>
      <p className="fl-results">الأدوار: {roles.length}</p>
      <div className="fl-table-wrap fl-stacked fl-stacked--checks">
        <div className="fl-table-scroll">
          <table className="fl-table">
            <thead>
              <tr>
                <th>الدور</th>
                {DOES.map((does) => <th key={does}>{offered.what[does]}</th>)}
                <th>عدد المستخدمين</th>
              </tr>
            </thead>
            <tbody>
              {roles.map((role) => (
                <tr key={role.id}>
                  <td className="fl-cell--id"><bdi>{role.name}</bdi></td>
                  {DOES.map((does) => (
                    <td key={does} data-label={offered.what[does]}>
                      <Checkbox disabled={busy === `${role.id}:${does}`}
                        checked={role.permissions.includes(form.keys[does])}
                        onChange={(on) => grant(role, does, on)} />
                    </td>
                  ))}
                  <td className="fl-cell--full" data-label="عدد المستخدمين" data-fl-num>{role.user_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {!roles.length && (
        <EmptyState icon="shield" title="لا توجد أدوار بعد">أضف دورًا من تبويب «الأدوار» أولًا.</EmptyState>
      )}
    </div>
  );
}

export default function Roles() {
  const [roles, setRoles] = useState(null);
  const [offered, setOffered] = useState({ forms: [], admin_pages: [], what: {} });
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [tab, setTab] = useState('roles');
  // null | { role } (role undefined for a new one)
  const [panel, setPanel] = useState(null);
  const toast = useToast();

  useEffect(() => {
    Promise.all([identityApi.listRoles(), identityApi.assignablePermissions()])
      .then(([loadedRoles, loadedOffered]) => {
        setRoles(loadedRoles);
        setOffered(loadedOffered);
      })
      .catch((err) => setError(err.message));
  }, []);

  const labels = useMemo(() => labelsOf(offered), [offered]);

  function open(next) {
    setError('');
    setPanel(next);
  }

  function saved(savedRole) {
    setRoles((current) => (current.some((r) => r.id === savedRole.id)
      ? current.map((r) => (r.id === savedRole.id ? savedRole : r))
      : [...current, savedRole]));
    if (panel) {
      toast(`تم حفظ الدور ${savedRole.name}`);
      setPanel(null);
    }
  }

  function deleted(role) {
    setRoles((current) => current.filter((r) => r.id !== role.id));
    toast(`تم حذف الدور ${role.name}`);
    setPanel(null);
  }

  const header = (
    <PageHeader title="الأدوار والصلاحيات"
      subtitle="لكل نموذج: من يعبّئه، من يرى طلبات الجميع، ومن يراجعها. النموذج الجديد مغلق حتى تُمنح صلاحيته."
      actions={<Button variant="primary" icon="plus" onClick={() => open({})}>إضافة دور</Button>} />
  );
  if (!roles) return <div className="fl-stack">{header}{error ? <Alert tone="error">{error}</Alert> : <Skeleton lines={5} />}</div>;

  const shown = roles.filter((role) => matchesQuery(query, role.name, ...role.permissions.map((key) => labels[key] || '')));
  return (
    <div className="fl-stack">
      {header}
      {error && <Alert tone="error">{error}</Alert>}
      <Tabs tabs={TABS} value={tab} onChange={setTab} label="طريقة العرض" />
      {tab === 'forms' ? (
        <FormAccess offered={offered} roles={roles} onSaved={saved} />
      ) : (
        <>
          <SearchInput value={query} onChange={setQuery} placeholder="ابحث باسم الدور أو الصلاحية" />
          <p className="fl-results">النتائج: {shown.length} من {roles.length}</p>
          {!shown.length ? (
            <EmptyState icon="shield" title={roles.length ? 'لا يوجد دور مطابق' : 'لا توجد أدوار بعد'}
              action={!roles.length && <Button icon="plus" onClick={() => open({})}>إضافة دور</Button>} />
          ) : (
            <div className="fl-table-wrap fl-stacked">
              <div className="fl-table-scroll">
                <table className="fl-table">
                  <thead><tr><th>اسم الدور</th><th>الصلاحيات</th><th>عدد المستخدمين</th><th>الإجراء</th></tr></thead>
                  <tbody>
                    {shown.map((role) => (
                      <tr key={role.id}>
                        <td className="fl-cell--id"><bdi>{role.name}</bdi></td>
                        <td className="fl-cell--wrap fl-cell--full" data-label="الصلاحيات">
                          <div className="fl-badges">
                            {role.permissions.length
                              ? role.permissions.map((key) => <Badge key={key} tone="brand">{labels[key] || key}</Badge>)
                              : <span className="fl-muted">بدون صلاحيات</span>}
                          </div>
                        </td>
                        <td className="fl-cell--full" data-label="عدد المستخدمين" data-fl-num>{role.user_count}</td>
                        <td className="fl-cell--actions"><Button size="sm" icon="edit" onClick={() => open({ role })}>تعديل</Button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
      {panel && (
        <RoleDrawer key={panel.role?.id ?? 'new'} role={panel.role} offered={offered}
          onSaved={saved} onDeleted={deleted} onClose={() => setPanel(null)} />
      )}
    </div>
  );
}
