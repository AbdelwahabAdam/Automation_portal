import { useEffect, useState } from 'react';
import { api } from './api.js';
import { Alert, Badge, Button, Card, Field, Loading, PageHeader, PasswordInput, TextInput } from './ds/index.jsx';

// Runs a form's request and keeps its busy, error and success state
function useAction() {
  const [state, setState] = useState({ busy: false, error: '', ok: '' });
  async function run(action, ok = '') {
    setState({ busy: true, error: '', ok: '' });
    try {
      await action();
      setState({ busy: false, error: '', ok });
    } catch (err) {
      setState({ busy: false, error: err.message, ok: '' });
    }
  }
  return [state, run];
}

function Feedback({ state }) {
  if (state.error) return <Alert tone="error">{state.error}</Alert>;
  return state.ok ? <Alert tone="success">{state.ok}</Alert> : null;
}

function Permissions({ account }) {
  const none = !account.is_admin && !account.manages.length && !account.roles.length;
  return (
    <div className="fl-badges">
      {account.is_admin && <Badge tone="warning" icon="shield">مدير النظام</Badge>}
      {account.manages.map((name) => <Badge key={name} tone="success">مدير {name}</Badge>)}
      {account.roles.map((name) => <Badge key={name} tone="brand">{name}</Badge>)}
      {none && <span className="fl-muted">بدون صلاحيات</span>}
    </div>
  );
}

function Profile({ account, onChange }) {
  const [fullName, setFullName] = useState(account.full_name);
  const [state, run] = useAction();
  const submit = (e) => {
    e.preventDefault();
    run(async () => onChange(await api('/account', { method: 'PUT', body: { full_name: fullName } })), 'تم حفظ الاسم.');
  };
  return (
    <form onSubmit={submit} noValidate>
      <Card title="بياناتي">
        <div className="fl-grid">
          <Field label="الاسم" htmlFor="acc_name">
            <TextInput id="acc_name" value={fullName} onChange={(e) => setFullName(e.target.value)} maxLength={120} required />
          </Field>
          <Field label="اسم المستخدم" htmlFor="acc_username" locked="للقراءة فقط">
            <TextInput id="acc_username" dir="ltr" value={account.username} readOnly />
          </Field>
          <Field label="البريد الإلكتروني" htmlFor="acc_email" locked="للقراءة فقط" hint="لتغيير البريد أو اسم المستخدم تواصل مع مدير النظام.">
            <TextInput id="acc_email" dir="ltr" value={account.email || 'لا يوجد'} readOnly />
          </Field>
          <Field label="الصلاحيات"><Permissions account={account} /></Field>
        </div>
        <Feedback state={state} />
        <div className="fl-row">
          <Button type="submit" variant="primary" loading={state.busy} disabled={!fullName.trim() || fullName.trim() === account.full_name}>حفظ</Button>
        </div>
      </Card>
    </form>
  );
}

function Password({ username }) {
  const [values, setValues] = useState({ current: '', next: '', repeat: '' });
  const [problem, setProblem] = useState('');
  const [state, run] = useAction();
  const set = (name) => (e) => setValues((current) => ({ ...current, [name]: e.target.value }));

  function submit(e) {
    e.preventDefault();
    if (!values.current) return setProblem('current');
    if (values.next.length < 8) return setProblem('next');
    if (values.next !== values.repeat) return setProblem('repeat');
    setProblem('');
    run(async () => {
      await api('/account/password', { method: 'POST', body: { current_password: values.current, new_password: values.next } });
      setValues({ current: '', next: '', repeat: '' });
    }, 'تم تغيير كلمة المرور.');
  }

  return (
    <form onSubmit={submit} noValidate>
      <Card title="كلمة المرور">
        {/* Lets the browser's password manager update the right account */}
        <input type="text" value={username} autoComplete="username" readOnly hidden />
        <div className="fl-grid">
          <Field label="كلمة المرور الحالية" htmlFor="pw_current" error={problem === 'current' ? 'اكتب كلمة المرور الحالية' : null}>
            <PasswordInput id="pw_current" value={values.current} onChange={set('current')} autoComplete="current-password" invalid={problem === 'current'} />
          </Field>
          <Field label="كلمة المرور الجديدة" htmlFor="pw_new" hint="8 أحرف على الأقل." error={problem === 'next' ? 'كلمة المرور 8 أحرف على الأقل' : null}>
            <PasswordInput id="pw_new" value={values.next} onChange={set('next')} maxLength={72} autoComplete="new-password" invalid={problem === 'next'} />
          </Field>
          <Field label="تأكيد كلمة المرور الجديدة" htmlFor="pw_repeat" error={problem === 'repeat' ? 'كلمتا المرور غير متطابقتين' : null}>
            <PasswordInput id="pw_repeat" value={values.repeat} onChange={set('repeat')} maxLength={72} autoComplete="new-password" invalid={problem === 'repeat'} />
          </Field>
        </div>
        <Feedback state={state} />
        <div className="fl-row"><Button type="submit" variant="primary" loading={state.busy}>تغيير كلمة المرور</Button></div>
      </Card>
    </form>
  );
}

// Two-step login by emailed code: always on for admins, a choice for everyone else
function TwoStep({ account, onChange }) {
  // null | 'confirm' (a code was emailed to turn it on) | 'off' (asking for the password to turn it off)
  const [step, setStep] = useState(null);
  const [hint, setHint] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [state, run] = useAction();
  // A refused code is cleared so the next one can be typed straight away
  useEffect(() => {
    if (state.error) setCode('');
  }, [state]);

  const sendCode = () => run(async () => {
    setHint((await api('/account/mfa/send-code', { method: 'POST' })).email_hint);
    setStep('confirm');
  });
  const enable = (e) => {
    e.preventDefault();
    run(async () => {
      const updated = await api('/account/mfa/enable', { method: 'POST', body: { code } });
      setStep(null);
      setCode('');
      onChange(updated);
    }, 'تم تفعيل التحقق بخطوتين.');
  };
  const disable = (e) => {
    e.preventDefault();
    run(async () => {
      const updated = await api('/account/mfa/disable', { method: 'POST', body: { password } });
      setStep(null);
      setPassword('');
      onChange(updated);
    }, 'تم إيقاف التحقق بخطوتين.');
  };

  let body;
  if (account.mfa_required) {
    body = <Alert tone="success" title="مفعّل دائمًا لمدير النظام">عند كل دخول يصلك رمز تحقق على بريدك <bdi dir="ltr">{account.email}</bdi>.</Alert>;
  } else if (step === 'confirm') {
    body = (
      <form onSubmit={enable} noValidate className="fl-stack fl-stack--sm">
        <Field label="رمز التحقق" htmlFor="on_code" hint={<>أرسلنا رمزًا من 6 أرقام إلى <bdi dir="ltr">{hint}</bdi>. اكتبه هنا للتأكد من أن البريد يصلك.</>}>
          <TextInput id="on_code" dir="ltr" inputMode="numeric" autoComplete="one-time-code" maxLength={8} value={code}
            onChange={(e) => setCode(e.target.value)} placeholder="123456" autoFocus />
        </Field>
        <Feedback state={state} />
        <div className="fl-row">
          <Button type="submit" variant="primary" loading={state.busy} disabled={!code.trim()}>تأكيد وتفعيل</Button>
          <Button onClick={() => setStep(null)}>إلغاء</Button>
        </div>
      </form>
    );
  } else if (step === 'off') {
    body = (
      <form onSubmit={disable} noValidate className="fl-stack fl-stack--sm">
        <Field label="كلمة المرور" htmlFor="off_password">
          <PasswordInput id="off_password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" autoFocus />
        </Field>
        <Feedback state={state} />
        <div className="fl-row">
          <Button type="submit" variant="destructive" loading={state.busy} disabled={!password}>إيقاف التحقق بخطوتين</Button>
          <Button onClick={() => setStep(null)}>إلغاء</Button>
        </div>
      </form>
    );
  } else if (account.mfa_enabled) {
    body = (
      <>
        <Alert tone="success" title="مفعّل">عند كل دخول يصلك رمز تحقق على بريدك <bdi dir="ltr">{account.email}</bdi>.</Alert>
        <Feedback state={state} />
        <div className="fl-row"><Button onClick={() => setStep('off')}>إيقاف</Button></div>
      </>
    );
  } else {
    body = (
      <>
        <p className="fl-muted" style={{ margin: 0 }}>حماية إضافية اختيارية: بعد كلمة المرور نرسل رمز تحقق إلى بريدك الإلكتروني وتكتبه للدخول.</p>
        <Feedback state={state} />
        {!account.email && <Alert tone="warning">لا يوجد بريد إلكتروني لحسابك. اطلب من مدير النظام إضافته أولًا.</Alert>}
        <div className="fl-row">
          <Button variant="primary" icon="shield" loading={state.busy} disabled={!account.email} onClick={sendCode}>تفعيل التحقق بخطوتين</Button>
        </div>
      </>
    );
  }

  return <Card title="التحقق بخطوتين">{body}</Card>;
}

export default function Account({ onUserChange }) {
  const [account, setAccount] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api('/account').then(setAccount).catch((err) => setError(err.message));
  }, []);

  // The header shows the name
  function changed(updated) {
    setAccount(updated);
    onUserChange();
  }

  const header = <PageHeader title="حسابي" subtitle="بياناتك وكلمة المرور والتحقق بخطوتين" />;
  if (!account) return <div className="fl-narrow fl-stack">{header}{error ? <Alert tone="error">{error}</Alert> : <Loading />}</div>;
  return (
    <div className="fl-narrow fl-stack">
      {header}
      <Profile account={account} onChange={changed} />
      <Password username={account.username} />
      <TwoStep account={account} onChange={changed} />
    </div>
  );
}
