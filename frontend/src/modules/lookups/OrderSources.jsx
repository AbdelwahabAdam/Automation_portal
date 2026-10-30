import { useEffect, useState } from 'react';
import * as lookupsApi from '../../api/lookups.js';
import { Alert, Badge, Button, Card, Field, Loading, PageHeader, TextInput, useConfirm } from '../../ds/index.jsx';

// Daftra's order sources (an invoice's «مصدر الطلب في دفترة»): adding one there, and turning one on or off
// (backend/app/order_sources.py). The sales forms offer the active ones.
export default function OrderSources() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [added, setAdded] = useState('');
  // The id of the source being turned on or off
  const [switching, setSwitching] = useState(null);
  const [confirmDialog, confirm] = useConfirm();

  useEffect(() => {
    lookupsApi.listOrderSources().then(setRows).catch((err) => setError(err.message));
  }, []);

  async function add(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    setAdded('');
    try {
      const source = await lookupsApi.addOrderSource(name);
      setRows((current) => [...(current || []), source]);
      setAdded(`تمت إضافة «${source.name}» في دفترة، ويظهر في نماذج المبيعات من الآن.`);
      setName('');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function setActive(row, active) {
    if (!active) {
      const yes = await confirm({
        title: `إيقاف «${row.name}»؟`, confirmLabel: 'إيقاف المصدر', tone: 'danger',
        body: 'لن يظهر في نماذج المبيعات بعد الآن، ولن تُرسَل مسودة اختارته حتى يُختار مصدر آخر. الفواتير السابقة لا تتغير، ويمكن تفعيله مرة أخرى.',
      });
      if (!yes) return;
    }
    setSwitching(row.id);
    setError('');
    setAdded('');
    try {
      const saved = await lookupsApi.setOrderSourceActive(row.id, active);
      setRows((current) => current.map((item) => (item.id === saved.id ? saved : item)));
    } catch (err) {
      setError(err.message);
    } finally {
      setSwitching(null);
    }
  }

  const active = rows ? rows.filter((row) => row.active).length : 0;
  // The ones the forms offer first, each group in Daftra's own order
  const shown = rows ? [...rows.filter((row) => row.active), ...rows.filter((row) => !row.active)] : [];
  return (
    <div className="fl-stack">
      {confirmDialog}
      <PageHeader title="مصادر الطلب" subtitle="مصادر الطلب في دفترة، التي يختار منها الموظف «مصدر الطلب في دفترة» في النماذج" />
      <form onSubmit={add} noValidate>
        <Card title="إضافة مصدر جديد">
          <p className="fl-muted fl-small fl-flush">يُضاف في دفترة مفعّلًا وفي آخر القائمة. لا يمكن إضافة اسم موجود (ولو اختلفت المسافات أو حالة الأحرف).</p>
          <Field label="اسم المصدر" htmlFor="source_name" required>
            <TextInput id="source_name" value={name} maxLength={100} placeholder="مثال: Website - جديد"
              onChange={(e) => setName(e.target.value)} />
          </Field>
          {added && <Alert tone="success">{added}</Alert>}
          {error && <Alert tone="error">{error}</Alert>}
          <div className="fl-row">
            <Button type="submit" variant="primary" icon="plus" loading={busy} disabled={name.trim().length < 2}>إضافة في دفترة</Button>
          </div>
        </Card>
      </form>
      <Card title={rows ? `المصادر في دفترة (${active} مفعّل من ${rows.length})` : 'المصادر في دفترة'}>
        {!rows ? (!error && <Loading />) : (
          <div className="fl-stack fl-stack--sm">
            <div className="fl-table-wrap">
              <table className="fl-table">
                <thead><tr><th>الاسم</th><th>الحالة</th><th>الترتيب</th><th>رقم دفترة</th><th></th></tr></thead>
                <tbody>
                  {shown.map((row) => (
                    <tr key={row.id}>
                      <td><bdi>{row.name}</bdi></td>
                      <td>{row.active
                        ? <Badge tone="success" icon="check-circle">مفعّل — يظهر في النماذج</Badge>
                        : <Badge tone="neutral">غير مفعّل</Badge>}
                      </td>
                      <td><bdi dir="ltr">{row.display_order}</bdi></td>
                      <td><bdi dir="ltr">{row.id}</bdi></td>
                      <td>
                        <Button size="sm" variant={row.active ? 'secondary' : 'primary'} icon={row.active ? 'x-circle' : 'check-circle'}
                          loading={switching === row.id} disabled={switching !== null} onClick={() => setActive(row, !row.active)}>
                          {row.active ? 'إيقاف' : 'تفعيل'}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="fl-field__hint fl-flush">تغيير اسم مصدر أو حذفه يتم من دفترة نفسها؛ لا تسمح دفترة بالحذف من خارجها.</p>
          </div>
        )}
      </Card>
    </div>
  );
}
