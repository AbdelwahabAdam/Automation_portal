// The catalog page's «الشروط والأحكام» tab: the versioned texts. Which one a package prints is
// chosen in the package's own editor.
import { useState } from 'react';
import * as termsApi from '../../api/terms.js';
import {
  Alert, Badge, Button, Drawer, EmptyState, Field, TextArea, TextInput, useConfirm,
} from '../../ds/index.jsx';
import { formatDate } from '../../lib/format.js';
import { useAction } from '../../lib/hooks.js';

// ---------- الشروط والأحكام ----------

// mode: 'new' (empty), 'version' (a copy of `term` as its next version) or 'view' (read only)
function TermDrawer({ mode, term, nextVersion, onSaved, onClose }) {
  const [values, setValues] = useState(() => (mode === 'new'
    ? { name: '', version: 1, body: '' }
    : { name: term.name, version: mode === 'version' ? nextVersion : term.version, body: term.body }));
  const { error, busy, run } = useAction();
  const [problem, setProblem] = useState('');
  const readOnly = mode === 'view';
  const set = (name, value) => setValues((current) => ({ ...current, [name]: value }));

  function submit(e) {
    e?.preventDefault();
    if (!values.name.trim() || !values.body.trim()) return setProblem('اكتب اسم الشروط ونصها.');
    if (!(Number.isInteger(Number(values.version)) && Number(values.version) >= 1)) return setProblem('رقم الإصدار رقم صحيح من 1 فأكثر.');
    setProblem('');
    run('save', async () => onSaved(await termsApi.createTerm({ ...values, version: Number(values.version) })));
  }

  return (
    <Drawer
      title={readOnly ? term.label : mode === 'version' ? 'إصدار جديد' : 'إضافة شروط وأحكام'}
      subtitle={readOnly
        ? 'لا يُعدَّل إصدار بعد حفظه؛ للتغيير أنشئ إصدارًا جديدًا ثم اختره في الباقات.'
        : 'يُحفظ كما هو ولا يُعدَّل بعد ذلك. يُطبع في آخر صفحة من الفاتورة بخط عريض، كل سطر فقرة.'}
      onClose={onClose} width="min(760px, 100vw)"
      footer={readOnly ? <Button onClick={onClose}>إغلاق</Button> : (
        <>
          <Button variant="primary" loading={busy === 'save'} disabled={Boolean(busy)} onClick={submit}>حفظ</Button>
          <Button onClick={onClose}>إلغاء</Button>
        </>
      )}
    >
      <form className="fl-stack fl-stack--sm" onSubmit={submit} noValidate>
        {(problem || error) && <Alert tone="error">{problem || error}</Alert>}
        <div className="fl-grid">
          <Field label="الاسم" htmlFor="t_name" required={!readOnly}>
            <TextInput id="t_name" value={values.name} onChange={(e) => set('name', e.target.value)} maxLength={200}
              readOnly={readOnly || mode === 'version'} />
          </Field>
          <Field label="رقم الإصدار" htmlFor="t_version" required={!readOnly}>
            <TextInput id="t_version" type="number" min="1" step="1" value={values.version}
              onChange={(e) => set('version', e.target.value)} readOnly={readOnly} />
          </Field>
        </div>
        <Field label="النص" htmlFor="t_body" required={!readOnly} hint={readOnly ? undefined : 'اترك سطرًا فارغًا لمسافة بين الفقرات.'}>
          <TextArea id="t_body" rows={18} value={values.body} onChange={(e) => set('body', e.target.value)} maxLength={20000} readOnly={readOnly} />
        </Field>
      </form>
    </Drawer>
  );
}

export function TermsTab({ terms, onChange, toast }) {
  // null | { mode, term }
  const [panel, setPanel] = useState(null);
  const [confirmDialog, confirm] = useConfirm();
  const { error, busy, run } = useAction();
  // The next free version of each name, for «إصدار جديد»
  const nextVersion = (name) => Math.max(0, ...terms.filter((t) => t.name === name).map((t) => t.version)) + 1;

  async function remove(term) {
    const yes = await confirm({ title: `حذف «${term.label}»؟`, body: 'يُحذف نهائيًا. لا تستخدمه أي باقة ولم يُطبع على أي فاتورة.', confirmLabel: 'حذف', tone: 'danger' });
    if (!yes) return;
    if (await run(`delete-${term.id}`, () => termsApi.deleteTerm(term.id))) {
      toast(`تم حذف ${term.label}.`);
      onChange();
    }
  }

  return (
    <>
      {confirmDialog}
      <div className="fl-row fl-row--spread">
        <p className="fl-field__hint">الإصدار لا يُعدَّل بعد حفظه. تُختار شروط كل باقة في تعديل الباقة. تطبع الفاتورة شروط أول باقة أُضيفت إلى الطلب ولها شروط.</p>
        <Button variant="primary" icon="plus" onClick={() => setPanel({ mode: 'new' })}>إضافة شروط</Button>
      </div>
      {error && <Alert tone="error">{error}</Alert>}
      {!terms.length ? (
        <EmptyState icon="file" title="لا توجد شروط بعد" />
      ) : (
        <div className="fl-table-wrap fl-stacked">
          <div className="fl-table-scroll">
            <table className="fl-table">
              <thead>
                <tr><th>الاسم</th><th>الإصدار</th><th>أُنشئ</th><th>في الباقات</th><th>طُبعت على</th><th>الإجراء</th></tr>
              </thead>
              <tbody>
                {terms.map((term) => (
                  <tr key={term.id}>
                    <td className="fl-cell--wrap"><strong>{term.name}</strong></td>
                    <td data-label="الإصدار" data-fl-num><Badge>{term.version}</Badge></td>
                    <td className="fl-cell--minor" data-label="أُنشئ">{formatDate(term.created_at)}</td>
                    <td data-label="في الباقات" data-fl-num>{term.assigned} باقة</td>
                    <td data-label="طُبعت على" data-fl-num>{term.printed} طلب</td>
                    <td className="fl-cell--actions">
                      <Button size="sm" onClick={() => setPanel({ mode: 'view', term })}>عرض</Button>
                      <Button size="sm" icon="plus" onClick={() => setPanel({ mode: 'version', term })}>إصدار جديد</Button>
                      {!term.assigned && !term.printed && (
                        <Button size="sm" variant="destructive-secondary" icon="trash" loading={busy === `delete-${term.id}`}
                          onClick={() => remove(term)}>حذف</Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {panel && (
        <TermDrawer
          key={`${panel.mode}-${panel.term?.id ?? 'new'}`} mode={panel.mode} term={panel.term}
          nextVersion={panel.term ? nextVersion(panel.term.name) : 1} onClose={() => setPanel(null)}
          onSaved={(saved) => { toast(`تم حفظ ${saved.label}.`); setPanel(null); onChange(); }}
        />
      )}
    </>
  );
}
