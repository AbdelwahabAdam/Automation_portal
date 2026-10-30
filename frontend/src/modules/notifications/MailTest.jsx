import { useEffect, useState } from 'react';
import * as mailApi from '../../api/notifications.js';
import { Alert, Button, Card, Field, Loading, PageHeader, Select, TextInput } from '../../ds/index.jsx';

// Sends any of the portal's emails, filled with made-up values, to an address the admin chooses
export default function MailTest() {
  const [settings, setSettings] = useState(null);
  const [template, setTemplate] = useState('');
  const [to, setTo] = useState('');
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  const [sent, setSent] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    mailApi.settings()
      .then((loaded) => {
        setSettings(loaded);
        setTemplate(loaded.templates[0].key);
        setTo(loaded.default_to);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!template) return undefined;
    let stale = false;
    setPreview(null);
    mailApi.preview(template)
      .then((loaded) => !stale && setPreview(loaded))
      .catch((err) => !stale && setError(err.message));
    return () => { stale = true; };
  }, [template]);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    setSent('');
    try {
      await mailApi.sendTest(template, to);
      setSent(`تم إرسال الرسالة إلى ${to.trim()}. إن لم تجدها في البريد الوارد فابحث في البريد غير المرغوب.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const header = <PageHeader title="اختبار البريد" subtitle="أرسل أي رسالة من رسائل البوابة بقيم تجريبية للتأكد من الإعدادات وشكل الرسالة" />;
  if (!settings) return <div className="fl-stack">{header}{error ? <Alert tone="error">{error}</Alert> : <Loading />}</div>;

  return (
    <div className="fl-stack">
      {header}
      {settings.configured ? (
        <Alert tone="info" title="إعدادات الإرسال">الإرسال عبر <bdi dir="ltr">{settings.server}</bdi> باسم <bdi dir="ltr">{settings.sender}</bdi>. القيم في الرسالة للتجربة فقط: الرابط والرمز لا يفتحان شيئًا.</Alert>
      ) : (
        <Alert tone="warning" title="البريد غير مُعدّ">أضف SMTP_HOST و MAIL_FROM في ملف ‎.env ثم أعد تشغيل الخادم.</Alert>
      )}
      <form onSubmit={submit} noValidate>
        <Card>
          <div className="fl-grid">
            <Field label="الرسالة" htmlFor="mail_template">
              <Select id="mail_template" value={template} onChange={(e) => setTemplate(e.target.value)}>
                {settings.templates.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
              </Select>
            </Field>
            <Field label="إلى" htmlFor="mail_to" required>
              <TextInput id="mail_to" type="email" value={to} onChange={(e) => setTo(e.target.value)} maxLength={254} />
            </Field>
          </div>
          {error && <Alert tone="error">{error}</Alert>}
          {sent && <Alert tone="success">{sent}</Alert>}
          <div className="fl-row">
            <Button type="submit" variant="primary" icon="send" loading={busy} disabled={!settings.configured || !to.trim()}>إرسال رسالة تجريبية</Button>
          </div>
        </Card>
      </form>
      <Card title="معاينة" actions={preview && <span className="fl-small fl-muted">العنوان: <bdi>{preview.subject}</bdi></span>}>
        {preview ? (
          // sandbox: the email is shown as a picture of itself; its links and scripts do nothing
          <iframe className="fl-preview-frame" title="معاينة الرسالة" sandbox="" srcDoc={preview.html} />
        ) : <Loading label="جارٍ تحميل المعاينة…" />}
      </Card>
    </div>
  );
}
