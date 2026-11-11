// The Daftra product a catalog product is linked to: the number, and a look at what is behind it.
//
// The number is what everything else follows — the sync, the invoice line, and صورة المنتج on the
// work order — so it is worth seeing before it is saved. The card under the field shows the Daftra
// product the number names: its picture, its name, its code and its price.
import { useEffect, useState } from 'react';
import * as catalogApi from '../../api/catalog.js';
import { Alert, Badge, Field, Icon, TextInput } from '../../ds/index.jsx';
import { formatMoney as money } from '../../lib/format.js';

const NUMBER = /^[1-9]\d*$/;
// How long after the last keystroke the number is looked up, so typing 3261 is one call, not four
const PAUSE = 400;

export function DaftraLink({ value, saved, productId, onChange }) {
  const [found, setFound] = useState(null);
  const [problem, setProblem] = useState('');
  const [busy, setBusy] = useState(false);
  const number = String(value ?? '').trim();
  const changed = NUMBER.test(number) && Number(number) !== saved;

  useEffect(() => {
    if (!NUMBER.test(number)) {
      setFound(null);
      setBusy(false);
      setProblem(number ? 'رقم منتج دفترة أرقام فقط، أكبر من صفر.' : 'غير مربوط بمنتج في دفترة.');
      return undefined;
    }
    let alive = true;
    setBusy(true);
    const timer = setTimeout(() => {
      catalogApi.daftraProduct(number).then(
        (row) => { if (alive) { setFound(row); setProblem(''); setBusy(false); } },
        (err) => { if (alive) { setFound(null); setProblem(err.message); setBusy(false); } },
      );
    }, PAUSE);
    return () => { alive = false; clearTimeout(timer); };
  }, [number]);

  // Held by another product of ours: saving would be refused, so it is said here first
  const heldByAnother = found?.linked_to && found.linked_to.id !== productId;

  return (
    <Field
      label="رقم المنتج في دفترة" htmlFor="p_daftra_id"
      hint={changed
        ? 'عند الحفظ يأخذ المنتج اسمه وسعره ووصفه وصورته وكوده من منتج دفترة الجديد، ولا يتغير شيء في دفترة.'
        : 'المنتج المربوط في دفترة: منه تأتي المزامنة، وصورته هي التي تُطبع على أمر العمل.'}
    >
      <TextInput
        id="p_daftra_id" inputMode="numeric" dir="ltr" value={number} maxLength={12}
        placeholder="مثال: 326" onChange={(e) => onChange(e.target.value.replace(/[^\d]/g, ''))}
      />
      <div className="fl-linkcard" aria-live="polite">
        {busy ? (
          <p className="fl-flush fl-small fl-muted">جارٍ القراءة من دفترة…</p>
        ) : !found ? (
          <p className="fl-flush fl-small fl-muted">{problem}</p>
        ) : (
          <>
            {found.image_url ? (
              <a className="fl-linkcard__shot" href={found.image_url} target="_blank" rel="noreferrer"
                title="فتح الصورة بالحجم الكامل">
                <img src={found.image_url} alt={`صورة ${found.name}`} />
              </a>
            ) : (
              <span className="fl-linkcard__shot fl-linkcard__shot--none"><Icon name="image" size={18} />لا صورة</span>
            )}
            <div className="fl-linkcard__body">
              <strong><bdi>{found.name || `منتج رقم ${found.daftra_id}`}</bdi></strong>
              <span className="fl-small fl-muted">
                <bdi dir="ltr">#{found.daftra_id}</bdi>
                {found.product_code && <> · كود <bdi dir="ltr">{found.product_code}</bdi></>}
                {found.unit_price != null && <> · {money(found.unit_price)} د.إ</>}
                {found.file_id && <> · صورة <bdi dir="ltr">{found.file_id}</bdi></>}
              </span>
              {found.description && <span className="fl-small fl-muted fl-linkcard__desc">{found.description}</span>}
              {!found.is_service && <Badge tone="warning">منتج مخزون — لا يُربط به</Badge>}
            </div>
          </>
        )}
      </div>
      {heldByAnother && (
        <Alert tone="error">هذا الرقم مربوط بمنتج آخر في البوابة: «{found.linked_to.name}». لن يُحفظ حتى يُفك عنه.</Alert>
      )}
    </Field>
  );
}
