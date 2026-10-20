import { useEffect, useMemo, useState } from 'react';
import { api } from '../api.js';
import {
  Alert, Badge, Button, Checkbox, Choice, Drawer, EmptyState, Field, Loading, PageHeader, Pager, SearchInput, Select, TextInput,
} from '../ds/index.jsx';
import { formatDate, matchesQuery } from '../formsMeta.js';

const EMPTY = { username: '', email: '', full_name: '', role_ids: [], manages: [], is_admin: false, is_active: true, daftra_staff_id: null };

function statusOf(user) {
  if (!user.is_active) return <Badge tone="neutral">موقوف</Badge>;
  if (!user.has_password) return <Badge tone="warning" icon="clock">بانتظار الدعوة</Badge>;
  return <Badge tone="success">نشط</Badge>;
}

function UserDrawer({ user, roles, departments, staff, isSelf, onSaved, onDeleted, onClose }) {
  const [values, setValues] = useState(
    user ? { ...EMPTY, ...user, email: user.email || '', role_ids: user.roles.map((role) => role.id) } : EMPTY,
  );
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const set = (name, value) => setValues((current) => ({ ...current, [name]: value }));

  // Runs one request for the drawer; on failure shows the message and unlocks the buttons
  async function run(name, action) {
    setBusy(name);
    setError('');
    try {
      await action();
    } catch (err) {
      setError(err.message);
      setBusy('');
    }
  }

  function submit(e) {
    e?.preventDefault();
    run('save', async () => {
      const { email, full_name, role_ids, manages, is_admin, is_active, username, daftra_staff_id } = values;
      if (user) {
        onSaved(await api(`/admin/users/${user.id}`, {
          method: 'PUT', body: { email, full_name, role_ids, manages, is_admin, is_active, daftra_staff_id },
        }));
      } else {
        const invite = await api('/admin/users', {
          method: 'POST', body: { username, email, full_name, role_ids, manages, is_admin, daftra_staff_id },
        });
        onSaved(invite.user, invite);
      }
    });
  }

  function resetMfa() {
    if (!window.confirm(`إيقاف التحقق بخطوتين للمستخدم ${user.username}؟`)) return;
    run('mfa', async () => onSaved(await api(`/admin/users/${user.id}/mfa-reset`, { method: 'POST' })));
  }

  function remove() {
    if (!window.confirm(`حذف المستخدم ${user.username} نهائيًا؟ لا يمكن التراجع.`)) return;
    run('delete', async () => {
      await api(`/admin/users/${user.id}`, { method: 'DELETE' });
      onDeleted(user);
    });
  }

  return (
    <Drawer
      title={user ? 'تعديل مستخدم' : 'إضافة مستخدم'}
      subtitle={user ? user.username : 'ستصله دعوة بالبريد فيها رابط لتعيين كلمة المرور.'}
      onClose={onClose}
      footer={(
        <>
          <Button variant="primary" loading={busy === 'save'} disabled={Boolean(busy)} onClick={submit}>{user ? 'حفظ' : 'حفظ وإرسال الدعوة'}</Button>
          <Button onClick={onClose}>إلغاء</Button>
          {user && !isSelf && (
            <span className="fl-push fl-row">
              {user.two_step && !user.is_admin && <Button size="sm" variant="tertiary" loading={busy === 'mfa'} onClick={resetMfa}>إيقاف التحقق بخطوتين</Button>}
              <Button size="sm" variant="destructive-secondary" icon="trash" loading={busy === 'delete'} onClick={remove}>حذف المستخدم</Button>
            </span>
          )}
        </>
      )}
    >
      <form className="fl-stack fl-stack--sm" onSubmit={submit} noValidate>
        {error && <Alert tone="error">{error}</Alert>}
        {!user && (
          <Field label="اسم المستخدم" htmlFor="u_username" required hint="حروف إنجليزية وأرقام فقط، بدون مسافات.">
            <TextInput id="u_username" dir="ltr" value={values.username} onChange={(e) => set('username', e.target.value)} autoComplete="off" />
          </Field>
        )}
        <Field label="الاسم الكامل" htmlFor="u_name" required>
          <TextInput id="u_name" value={values.full_name} onChange={(e) => set('full_name', e.target.value)} maxLength={120} />
        </Field>
        <Field label="البريد الإلكتروني" htmlFor="u_email" required hint="يُستخدم للدخول وللإشعارات.">
          <TextInput id="u_email" dir="ltr" type="email" value={values.email} onChange={(e) => set('email', e.target.value)} maxLength={254} autoComplete="off" />
        </Field>
        <Field
          label="الموظف في دفترة" htmlFor="u_daftra"
          hint={staff ? 'يظهر اسمه كمندوب المبيعات على الفواتير التي تُنشأ في دفترة عند اعتماد طلباته.' : 'تعذر تحميل موظفي دفترة الآن.'}
        >
          <Select
            id="u_daftra" value={values.daftra_staff_id == null ? '' : String(values.daftra_staff_id)} disabled={!staff}
            onChange={(e) => set('daftra_staff_id', e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">غير مربوط</option>
            {(staff || []).map((member) => <option key={member.id} value={String(member.id)}>{member.name}</option>)}
            {/* A link to someone no longer active in Daftra stays visible instead of silently clearing */}
            {staff && values.daftra_staff_id != null && !staff.some((m) => m.id === values.daftra_staff_id) && (
              <option value={String(values.daftra_staff_id)}>موظف رقم {values.daftra_staff_id} (غير نشط في دفترة)</option>
            )}
          </Select>
        </Field>
        <Field label="الأدوار" hint={roles.length ? null : 'لا توجد أدوار بعد. أضف دورًا من «الأدوار والصلاحيات».'}>
          {roles.length > 0 && (
            <Choice name="u_roles" multiple options={roles.map((role) => ({ value: role.id, label: role.name }))}
              value={values.role_ids} onChange={(v) => set('role_ids', v)} />
          )}
        </Field>
        <Field label="مدير قسم" hint="مدير القسم يفتح كل صفحات قسمه، ومنها «طلبات الفريق» في المبيعات.">
          <Choice name="u_manages" multiple options={departments.map((d) => ({ value: d.key, label: d.label }))}
            value={values.manages} onChange={(v) => set('manages', v)} />
        </Field>
        <div className="fl-stack fl-stack--sm">
          <Checkbox checked={values.is_admin} disabled={isSelf} onChange={(v) => set('is_admin', v)}>
            مدير النظام — يفتح كل الصفحات ويدير المستخدمين، ويدخل دائمًا برمز تحقق يصله بالبريد
          </Checkbox>
          {user && (
            <Checkbox checked={values.is_active} disabled={isSelf} onChange={(v) => set('is_active', v)}>الحساب نشط</Checkbox>
          )}
          {isSelf && <p className="fl-field__hint">لا يمكنك إيقاف حسابك أو حذفه أو إزالة صلاحية المدير عن نفسك.</p>}
        </div>
      </form>
    </Drawer>
  );
}

// The outcome of sending a password link: a confirmation, or the link itself when the email failed
function InviteResult({ invite, onDismiss }) {
  const [copied, setCopied] = useState(false);
  if (invite.email_sent) {
    return <Alert tone="success" onDismiss={onDismiss}>تم إرسال رابط تعيين كلمة المرور إلى <bdi dir="ltr">{invite.user.email}</bdi>.</Alert>;
  }
  return (
    <Alert
      tone="warning" title={`تعذر إرسال البريد إلى ${invite.user.email}`} onDismiss={onDismiss}
      actions={<Button size="sm" icon="copy" onClick={() => navigator.clipboard.writeText(invite.link).then(() => setCopied(true))}>{copied ? 'تم النسخ' : 'نسخ الرابط'}</Button>}
    >
      انسخ الرابط وأرسله للمستخدم <bdi>{invite.user.username}</bdi> بنفسك:
      <div dir="ltr" style={{ marginBlockStart: 'var(--fl-space-2)', overflowWrap: 'anywhere' }}>{invite.link}</div>
    </Alert>
  );
}

export default function Users({ user: me }) {
  const [users, setUsers] = useState(null);
  const [roles, setRoles] = useState([]);
  const [departments, setDepartments] = useState([]);
  // Daftra's active staff, to link a user to; null until loaded, or if Daftra cannot be reached
  const [staff, setStaff] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  // null | { mode: 'new' } | { mode: 'edit', user }
  const [panel, setPanel] = useState(null);
  const [invite, setInvite] = useState(null);
  const [sendingTo, setSendingTo] = useState(null);
  const [query, setQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  useEffect(() => {
    Promise.all([api('/admin/users'), api('/admin/roles'), api('/admin/departments')])
      .then(([loadedUsers, loadedRoles, loadedDepartments]) => {
        setUsers(loadedUsers);
        setRoles(loadedRoles);
        setDepartments(loadedDepartments);
      })
      .catch((err) => setError(err.message));
    api('/admin/daftra/staff').then(setStaff).catch(() => {});
  }, []);
  useEffect(() => setPage(1), [query, roleFilter, statusFilter, pageSize]);

  const departmentLabels = Object.fromEntries(departments.map((department) => [department.key, department.label]));
  const filtered = useMemo(() => (users || []).filter((u) => matchesQuery(query, u.full_name, u.username, u.email || '')
    && (!roleFilter || (roleFilter === 'admin' ? u.is_admin : u.roles.some((r) => String(r.id) === roleFilter)))
    && (!statusFilter || (statusFilter === 'active' && u.is_active && u.has_password)
      || (statusFilter === 'invited' && u.is_active && !u.has_password) || (statusFilter === 'inactive' && !u.is_active))),
  [users, query, roleFilter, statusFilter]);

  function open(next) {
    setNotice('');
    setInvite(null);
    setError('');
    setPanel(next);
  }

  async function sendLink(user) {
    const question = user.has_password
      ? `إرسال رابط لتعيين كلمة مرور جديدة إلى ${user.email}؟`
      : `إعادة إرسال الدعوة إلى ${user.email}؟`;
    if (!window.confirm(question)) return;
    open(null);
    setSendingTo(user.id);
    try {
      setInvite(await api(`/admin/users/${user.id}/invite`, { method: 'POST' }));
    } catch (err) {
      setError(err.message);
    } finally {
      setSendingTo(null);
    }
  }

  function saved(savedUser, sentInvite) {
    setUsers((current) => (current.some((u) => u.id === savedUser.id)
      ? current.map((u) => (u.id === savedUser.id ? savedUser : u))
      : [...current, savedUser]));
    setNotice(`تم حفظ المستخدم ${savedUser.username}.`);
    setInvite(sentInvite || null);
    setPanel(null);
  }

  function deleted(deletedUser) {
    setUsers((current) => current.filter((u) => u.id !== deletedUser.id));
    setNotice(`تم حذف المستخدم ${deletedUser.username}.`);
    setPanel(null);
  }

  const header = (
    <PageHeader title="المستخدمون" subtitle="عرض حسابات الموظفين وإضافة مستخدم جديد"
      actions={<Button variant="primary" icon="plus" onClick={() => open({ mode: 'new' })}>إضافة مستخدم</Button>} />
  );
  if (!users) return <div className="fl-stack">{header}{error ? <Alert tone="error">{error}</Alert> : <Loading />}</div>;

  const shown = filtered.slice((page - 1) * pageSize, page * pageSize);
  return (
    <div className="fl-stack">
      {header}
      {notice && <Alert tone="success" onDismiss={() => setNotice('')}>{notice}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}
      {invite && <InviteResult key={invite.link || invite.user.id} invite={invite} onDismiss={() => setInvite(null)} />}
      <div className="fl-filters">
        <div className="fl-filters__search">
          <Field label="بحث" htmlFor="users_search" hideLabel>
            <SearchInput id="users_search" value={query} onChange={setQuery} placeholder="ابحث بالاسم أو اسم المستخدم أو البريد الإلكتروني" />
          </Field>
        </div>
        <Field label="الدور" htmlFor="users_role">
          <Select id="users_role" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
            <option value="">كل الأدوار</option>
            <option value="admin">مدير النظام</option>
            {roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
          </Select>
        </Field>
        <Field label="حالة الحساب" htmlFor="users_status">
          <Select id="users_status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">كل الحالات</option>
            <option value="active">نشط</option>
            <option value="invited">بانتظار الدعوة</option>
            <option value="inactive">موقوف</option>
          </Select>
        </Field>
      </div>
      <p className="fl-results">النتائج: {filtered.length} من {users.length}</p>
      {!filtered.length ? (
        <EmptyState icon="users" title="لا يوجد مستخدم مطابق">غيّر البحث أو الفلاتر.</EmptyState>
      ) : (
        <div className="fl-table-wrap">
          <div className="fl-table-scroll">
            <table className="fl-table">
              <thead>
                <tr><th>الاسم الكامل</th><th>البريد الإلكتروني</th><th>الصلاحيات</th><th>حالة الحساب</th><th>تاريخ الإضافة</th><th>الإجراء</th></tr>
              </thead>
              <tbody>
                {shown.map((user) => (
                  <tr key={user.id} className={user.is_active ? undefined : 'fl-row--off'}>
                    <td className="fl-cell--wrap">
                      <strong><bdi>{user.full_name}</bdi></strong>
                      <span className="fl-cell__sub"><bdi dir="ltr">{user.username}</bdi></span>
                    </td>
                    <td>{user.email ? <bdi dir="ltr">{user.email}</bdi> : <Badge tone="error">لا يوجد</Badge>}</td>
                    <td className="fl-cell--wrap">
                      <div className="fl-badges">
                        {user.is_admin && <Badge tone="warning" icon="shield">مدير النظام</Badge>}
                        {user.manages.map((key) => <Badge key={key} tone="success">مدير {departmentLabels[key] || key}</Badge>)}
                        {user.roles.map((role) => <Badge key={role.id} tone="brand">{role.name}</Badge>)}
                        {!user.is_admin && !user.roles.length && !user.manages.length && <span className="fl-muted">بدون صلاحيات</span>}
                      </div>
                    </td>
                    <td>
                      <div className="fl-badges">{statusOf(user)}{user.two_step && user.is_active && <Badge tone="info" icon="shield">بخطوتين</Badge>}</div>
                    </td>
                    <td className="fl-cell--nowrap"><bdi dir="ltr">{formatDate(user.created_at)}</bdi></td>
                    <td className="fl-cell--actions">
                      <Button size="sm" icon="edit" onClick={() => open({ mode: 'edit', user })}>تعديل</Button>
                      {user.is_active && user.email && (
                        <Button size="sm" variant="tertiary" icon="mail" loading={sendingTo === user.id} onClick={() => sendLink(user)}>
                          {user.has_password ? 'رابط كلمة المرور' : 'إعادة الدعوة'}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={page} pageSize={pageSize} total={filtered.length} onPage={setPage} onPageSize={setPageSize} />
        </div>
      )}
      {panel && (
        <UserDrawer
          key={panel.user?.id ?? 'new'}
          user={panel.user}
          roles={roles}
          departments={departments}
          staff={staff}
          isSelf={panel.user?.id === me.id}
          onSaved={saved}
          onDeleted={deleted}
          onClose={() => setPanel(null)}
        />
      )}
    </div>
  );
}
