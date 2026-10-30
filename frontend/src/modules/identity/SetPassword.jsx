import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import * as identityApi from '../../api/identity.js';
import { Alert, Button, Field, Loading, PasswordInput } from '../../ds/index.jsx';
import { AuthCard } from './Login.jsx';

// Opened from the link in an invitation or password reset email
export default function SetPassword({ onDone }) {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  // null while checking the link, then { username, full_name, invited } or { invalid: message }
  const [link, setLink] = useState(null);
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    identityApi.whosePasswordLink(token)
      .then(setLink)
      .catch((err) => setLink({ invalid: err.message }));
  }, [token]);

  async function submit(e) {
    e.preventDefault();
    if (password.length < 8) return setErrors({ password: 'كلمة المرور 8 أحرف على الأقل' });
    if (password !== repeat) return setErrors({ repeat: 'كلمتا المرور غير متطابقتين' });
    setBusy(true);
    setErrors({});
    try {
      await identityApi.setPassword(token, password);
      onDone('تم تعيين كلمة المرور. سجّل الدخول الآن.');
    } catch (err) {
      setErrors({ form: err.message });
      setBusy(false);
    }
  }

  if (!link) return <AuthCard title="تعيين كلمة المرور"><Loading label="جارٍ التحقق من الرابط…" /></AuthCard>;
  if (link.invalid) {
    return (
      <AuthCard title="الرابط غير صالح" footer={<Button variant="tertiary" icon="arrow-start" onClick={() => onDone('')}>صفحة تسجيل الدخول</Button>}>
        <Alert tone="error">{link.invalid}</Alert>
      </AuthCard>
    );
  }
  return (
    <AuthCard
      title={link.invited ? 'أهلًا بك' : 'كلمة مرور جديدة'}
      subtitle={<>{link.invited ? 'اختر كلمة مرور لحسابك' : 'كلمة مرور جديدة للحساب'} <bdi>{link.full_name || link.username}</bdi></>}
      onSubmit={submit}
    >
      {/* Lets the browser's password manager save the new password under the right account */}
      <input type="text" value={link.username} autoComplete="username" readOnly hidden />
      {errors.form && <Alert tone="error">{errors.form}</Alert>}
      <Field label="كلمة المرور الجديدة" htmlFor="new_password" hint="8 أحرف على الأقل." error={errors.password}>
        <PasswordInput id="new_password" value={password} onChange={(e) => setPassword(e.target.value)} maxLength={72} autoComplete="new-password" autoFocus invalid={Boolean(errors.password)} />
      </Field>
      <Field label="تأكيد كلمة المرور" htmlFor="repeat_password" error={errors.repeat}>
        <PasswordInput id="repeat_password" value={repeat} onChange={(e) => setRepeat(e.target.value)} maxLength={72} autoComplete="new-password" invalid={Boolean(errors.repeat)} />
      </Field>
      <Button type="submit" variant="primary" size="lg" full loading={busy}>حفظ كلمة المرور</Button>
    </AuthCard>
  );
}
