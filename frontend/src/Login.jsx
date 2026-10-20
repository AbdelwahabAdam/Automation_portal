import { useState } from 'react';
import { api, setToken } from './api.js';
import { Alert, Button, Field, PasswordInput, TextInput } from './ds/index.jsx';

const BRAND = 'المستقبل لايف';

export function AuthCard({ title, subtitle, children, footer, onSubmit }) {
  return (
    <main className="fl-auth">
      <form className="fl-auth__card" onSubmit={onSubmit} noValidate>
        <div className="fl-auth__brand">{BRAND}</div>
        <h1 className="fl-auth__title">{title}</h1>
        {subtitle && <p className="fl-auth__sub">{subtitle}</p>}
        {children}
        {footer && <div className="fl-auth__foot">{footer}</div>}
      </form>
    </main>
  );
}

function ForgotPassword({ initial, onBack }) {
  const [username, setUsername] = useState(initial);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (!username.trim()) return setError('اكتب البريد الإلكتروني أو اسم المستخدم');
    setBusy(true);
    setError('');
    try {
      await api('/auth/forgot-password', { method: 'POST', body: { username } });
      setSent(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="استعادة كلمة المرور"
      subtitle={sent ? null : 'سنرسل إلى بريدك رابطًا لتعيين كلمة مرور جديدة.'}
      onSubmit={submit}
      footer={<Button variant="tertiary" icon="arrow-start" onClick={onBack}>رجوع لتسجيل الدخول</Button>}
    >
      {sent ? (
        <Alert tone="success" title="تحقق من بريدك">إذا كان الحساب موجودًا فستصلك رسالة فيها رابط لتعيين كلمة مرور جديدة.</Alert>
      ) : (
        <>
          <Field label="البريد الإلكتروني أو اسم المستخدم" htmlFor="forgot_user" error={error}>
            <TextInput id="forgot_user" dir="ltr" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus invalid={Boolean(error)} />
          </Field>
          <Button type="submit" variant="primary" size="lg" full loading={busy}>إرسال الرابط</Button>
        </>
      )}
    </AuthCard>
  );
}

export default function Login({ onLogin, notice }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [forgot, setForgot] = useState(false);
  // Second step: the password was accepted and a code was emailed. Holds { email_hint } then
  const [needsCode, setNeedsCode] = useState(null);
  const [code, setCode] = useState('');
  const [resent, setResent] = useState('');

  async function submit(e) {
    e.preventDefault();
    if (!needsCode && (!username.trim() || !password)) return setError('اكتب البريد الإلكتروني أو اسم المستخدم وكلمة المرور');
    if (needsCode && !code.trim()) return setError('اكتب رمز التحقق');
    setBusy(true);
    setError('');
    try {
      const result = await api('/auth/login', { method: 'POST', body: { username, password, code: needsCode ? code : '' } });
      if (result.mfa_required) {
        setNeedsCode(result);
      } else {
        setToken(result.access_token);
        onLogin(result.user);
      }
    } catch (err) {
      setError(err.message);
      setCode('');
    } finally {
      setBusy(false);
    }
  }

  function startOver() {
    setNeedsCode(null);
    setCode('');
    setPassword('');
    setError('');
    setResent('');
  }

  // Logging in again without a code makes the server send a new one, unless one just went out
  async function resend() {
    setBusy(true);
    setError('');
    setResent('');
    try {
      const result = await api('/auth/login', { method: 'POST', body: { username, password, code: '' } });
      setResent(result.resend_in < 60 ? `أُرسل رمز قبل قليل. يمكنك طلب رمز جديد بعد ${result.resend_in} ثانية.` : 'أرسلنا رمزًا جديدًا.');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (forgot) return <ForgotPassword initial={username} onBack={() => setForgot(false)} />;
  if (needsCode) {
    return (
      <AuthCard
        title="التحقق بخطوتين"
        subtitle={<>أرسلنا رمزًا من 6 أرقام إلى بريدك <bdi dir="ltr">{needsCode.email_hint}</bdi>. الرمز صالح 10 دقائق.</>}
        onSubmit={submit}
        footer={(
          <>
            <Button variant="tertiary" icon="refresh" disabled={busy} onClick={resend}>لم يصلني الرمز، أرسله مرة أخرى</Button>
            <Button variant="tertiary" icon="arrow-start" onClick={startOver}>رجوع</Button>
          </>
        )}
      >
        <Field label="رمز التحقق" htmlFor="login_code" error={error} hint={resent || null}>
          <TextInput id="login_code" dir="ltr" inputMode="numeric" autoComplete="one-time-code" maxLength={8} value={code}
            onChange={(e) => setCode(e.target.value)} placeholder="123456" autoFocus invalid={Boolean(error)} />
        </Field>
        <Button type="submit" variant="primary" size="lg" full loading={busy}>تأكيد</Button>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="تسجيل الدخول"
      subtitle="ادخل بيانات حسابك للوصول إلى البوابة"
      onSubmit={submit}
      footer={(
        <>
          <Button variant="tertiary" icon="help" onClick={() => setForgot(true)}>نسيت كلمة المرور؟</Button>
          <span>للحصول على حساب أو مساعدة في الدخول، تواصل مع مسؤول النظام.</span>
        </>
      )}
    >
      {notice && <Alert tone="success">{notice}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}
      <Field label="البريد الإلكتروني أو اسم المستخدم" htmlFor="login_user">
        <TextInput id="login_user" dir="ltr" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus />
      </Field>
      <Field label="كلمة المرور" htmlFor="login_password">
        <PasswordInput id="login_password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
      </Field>
      <Button type="submit" variant="primary" size="lg" full loading={busy}>{busy ? 'جارٍ الدخول…' : 'تسجيل الدخول'}</Button>
    </AuthCard>
  );
}
