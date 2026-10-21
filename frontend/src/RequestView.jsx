import { useEffect, useState } from 'react';
import { api, openAttachment } from './api.js';
import { FileRow } from './attachments.jsx';
import {
  ActionBar, Alert, Badge, Button, Card, Dialog, Field, Icon, Loading, PageHeader, StatusBadge, TextArea,
} from './ds/index.jsx';
import { formatAmount, formatDate, formatDay, formatMoney } from './formsMeta.js';
import { DAFTRA_LIST_TYPES, groupLines } from './validation.js';

// The PDFs approving a request saves on it (see backend/app/daftra_sync/)
const DAFTRA_PDFS = [['daftra_invoice', 'الفاتورة PDF'], ['daftra_receipt', 'سند القبض PDF'], ['daftra_work_order', 'أمر الشغل PDF']];

// What approving the request created in Daftra, or why it could not be created
function DaftraCard({ request }) {
  const pdfs = DAFTRA_PDFS
    .map(([field, label]) => [label, request.attachments.find((a) => a.field === field)])
    .filter(([, file]) => file);
  if (!request.daftra_invoice_no && !request.daftra_error) return null;
  return (
    <Card title="دفترة">
      {request.daftra_error && (
        <Alert tone="error" title="تعذر إكمال الإنشاء في دفترة">
          {request.daftra_error}
          {request.status === 'submitted' && <p>بعد حل المشكلة اعتمد الطلب مرة أخرى؛ يُكمل من حيث توقف ولا يكرر ما أُنشئ.</p>}
        </Alert>
      )}
      <dl className="fl-dl">
        {request.daftra_invoice_no && <div><dt>رقم الفاتورة</dt><dd><bdi dir="ltr">{request.daftra_invoice_no}</bdi></dd></div>}
        {request.daftra_receipt_no && <div><dt>رقم سند القبض</dt><dd><bdi dir="ltr">{request.daftra_receipt_no}</bdi></dd></div>}
        {request.daftra_work_order_no && <div><dt>رقم أمر الشغل</dt><dd><bdi dir="ltr">{request.daftra_work_order_no}</bdi></dd></div>}
        {pdfs.map(([label, file]) => (
          <div key={file.id}>
            <dt>{label}</dt>
            <dd>
              <button type="button" className="fl-link fl-row" onClick={() => openAttachment(file.id)}>
                <Icon name="file-text" size={16} /><bdi>{file.filename}</bdi>
              </button>
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

// The request at a glance, above its sections: who it is for and what it comes to
const SUMMARY_MONEY = [['total_amount', 'الإجمالي'], ['paid_amount', 'المدفوع'], ['remaining_amount', 'المتبقي']];

function Summary({ request }) {
  const data = request.data;
  const place = [data.emirate, data.area].filter(Boolean).join('، ');
  const facts = [
    ['العميل', data.customer_name && <bdi>{data.customer_name}</bdi>],
    ['الهاتف', data.phone && <bdi dir="ltr">{data.phone}</bdi>],
    ['كود العميل', data.client_code && <bdi dir="ltr">{data.client_code}</bdi>],
    ['المنطقة', place],
  ].filter(([, value]) => value);
  const money = SUMMARY_MONEY.filter(([name]) => typeof data[name] === 'number');
  const daftra = [
    ['الفاتورة', request.daftra_invoice_no], ['سند القبض', request.daftra_receipt_no], ['أمر الشغل', request.daftra_work_order_no],
  ].filter(([, value]) => value);
  if (!facts.length && !money.length) return null;
  return (
    <section className="fl-summary" aria-label="ملخص الطلب">
      {facts.length > 0 && (
        <dl className="fl-summary__facts">
          {facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
        </dl>
      )}
      {money.length > 0 && (
        <dl className="fl-summary__money">
          {money.map(([name, label]) => (
            <div key={name} className={name === 'remaining_amount' && data[name] > 0 ? 'fl-summary__due' : undefined}>
              <dt>{label}</dt>
              <dd data-fl-num><bdi dir="ltr">{formatMoney(data[name])}</bdi> <span className="fl-totals__unit">درهم</span></dd>
            </div>
          ))}
        </dl>
      )}
      {daftra.length > 0 && (
        <div className="fl-badges">
          {daftra.map(([label, value]) => <Badge key={label} tone="success" icon="check-circle">{label} <bdi dir="ltr">{value}</bdi></Badge>)}
        </div>
      )}
    </section>
  );
}

const EVENT_LOOK = {
  created: ['file', 'neutral'],
  submitted: ['send', 'info'],
  resubmitted: ['send', 'info'],
  returned: ['arrow-start', 'warning'],
  approved: ['check-circle', 'success'],
};

function History({ events }) {
  return (
    <Card title="سجل الطلب">
      <ol className="fl-timeline">
        {events.map((event, index) => {
          const [icon, tone] = EVENT_LOOK[event.kind] || ['dot', 'neutral'];
          return (
            <li key={index} className="fl-timeline__item">
              <span className={`fl-timeline__dot fl-timeline__dot--${tone}`}><Icon name={icon} size={16} /></span>
              <div className="fl-timeline__body">
                <span className="fl-timeline__title">{event.label}{event.revision > 1 && ` — النسخة ${event.revision}`}</span>
                <span className="fl-timeline__meta"><bdi>{event.username}</bdi> · <bdi dir="ltr">{formatDate(event.at)}</bdi></span>
                {event.note && <div className="fl-timeline__note">{event.note}</div>}
              </div>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

// Approve, or return to the salesperson with a reason; the decision is tied to the revision on screen
// daftraNote: what approving creates in Daftra, from the form's definition (backend/app/forms/definitions.py "daftra_note")
function ReviewActions({ request, own, daftraNote, onDone }) {
  // null | 'approve' | 'return'
  const [asking, setAsking] = useState(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function decide(kind) {
    setBusy(true);
    setError('');
    try {
      const body = kind === 'approve' ? { revision: request.revision } : { revision: request.revision, reason };
      await api(`/review/requests/${request.id}/${kind}`, { method: 'POST', body });
      onDone(kind === 'approve' ? `تم اعتماد الطلب رقم ${request.id}.` : `تمت إعادة الطلب رقم ${request.id} للتعديل.`);
    } catch (err) {
      setError(err.message);
      setBusy(false);
      setAsking(null);
    }
  }

  if (request.status !== 'submitted') return null;
  return (
    <>
      <ActionBar message={(own || error) && (
        <>
          {own && <Alert tone="info">هذا طلبك؛ يراجعه مدير آخر.</Alert>}
          {error && <Alert tone="error">{error}</Alert>}
        </>
      )}>
        <Button variant="primary" icon="check-circle" disabled={own} onClick={() => setAsking('approve')}>اعتماد الطلب</Button>
        <Button icon="arrow-start" disabled={own} onClick={() => setAsking('return')}>إعادة للتعديل</Button>
      </ActionBar>
      {asking === 'approve' && (
        <Dialog title="اعتماد الطلب؟" confirmLabel="اعتماد" busy={busy} onConfirm={() => decide('approve')} onCancel={() => setAsking(null)}>
          بعد الاعتماد لا يمكن تعديل الطلب، ويصل إشعار بالبريد إلى الموظف.
          {daftraNote && ` ${daftraNote}`}
        </Dialog>
      )}
      {asking === 'return' && (
        <Dialog
          title="إعادة الطلب للتعديل" confirmLabel="إعادة للتعديل" busy={busy} confirmDisabled={reason.trim().length < 5}
          onConfirm={() => decide('return')} onCancel={() => setAsking(null)}
        >
          <Field label="المطلوب تعديله" htmlFor="return_reason" required hint="يظهر للموظف في الطلب ويصله بالبريد.">
            <TextArea id="return_reason" rows={4} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={2000} />
          </Field>
        </Dialog>
      )}
    </>
  );
}

// One request, read-only. With review set, a manager can approve or return it.
export default function RequestView({ requestId, formTypes, onBack, ownerName, review, actions }) {
  const [request, setRequest] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([api(`/requests/${requestId}`), api(`/requests/${requestId}/history`)])
      .then(([loaded, history]) => { setRequest(loaded); setEvents(history); })
      .catch((err) => setError(err.message));
  }, [requestId]);

  const back = <Button className="fl-back" variant="tertiary" icon="arrow-start" onClick={onBack}>رجوع</Button>;
  if (error) return <div className="fl-stack">{back}<Alert tone="error">{error}</Alert></div>;
  if (!request) return <Loading />;

  const formType = formTypes.find((type) => type.key === request.form_type);
  if (!formType) return <div className="fl-stack">{back}<Alert tone="error">نوع هذا النموذج لم يعد متاحًا.</Alert></div>;

  function display(spec) {
    if (spec.type === 'order_lines') {
      const lines = request.data[spec.name];
      if (!Array.isArray(lines) || !lines.length) return null;
      const lineFields = spec.line_fields || [];
      // Lines from the same package pick are shown under its name, in the order first added
      return (
        <span className="fl-stack fl-stack--sm">
          {groupLines(lines).map((group) => {
            const first = group.rows[0].line;
            const indent = group.groupName ? 'fl-indent' : undefined;
            // The details describe the package (or the one standalone product) as a whole, not each item inside it
            const details = lineFields
              .map((dspec) => [dspec.label, first.details?.[dspec.name]])
              .filter(([, v]) => v != null && v !== '');
            return (
              <span key={group.key} className="fl-stack fl-stack--sm">
                {group.groupName && (
                  <bdi>
                    <strong>{group.groupName}</strong>
                    {Number(first.details?.package_quantity) > 1 && <span data-fl-num> × {first.details.package_quantity}</span>}
                  </bdi>
                )}
                {group.rows.map(({ line, index }) => (
                  <bdi key={index} className={indent}>
                    {line.name} × <span data-fl-num>{line.quantity}</span>
                    {typeof line.unit_price === 'number' && <span className="fl-muted" data-fl-num> — {formatMoney(line.unit_price)} درهم</span>}
                  </bdi>
                ))}
                {details.length > 0 && (
                  <dl className={['fl-dl', indent].filter(Boolean).join(' ')}>
                    {details.map(([label, v]) => <div key={label}><dt>{label}</dt><dd><bdi>{v}</bdi></dd></div>)}
                  </dl>
                )}
              </span>
            );
          })}
        </span>
      );
    }
    if (spec.type === 'files') {
      const files = request.attachments.filter((a) => a.field === spec.name);
      // The pictures themselves: a reviewer sees the payment proof without opening each one
      return files.length ? (
        <span className="fl-files">
          {files.map((file) => <FileRow key={file.id} file={file} />)}
        </span>
      ) : null;
    }
    const value = DAFTRA_LIST_TYPES.includes(spec.type) ? request.data[`${spec.name}_name`] || request.data[spec.name] : request.data[spec.name];
    if (value == null || value === '') return null;
    // Amounts and dates are read the way the rest of the portal writes them
    if (spec.money && typeof value === 'number') return <bdi data-fl-num>{formatAmount(value)}</bdi>;
    if (spec.type === 'date') return <bdi data-fl-num>{formatDay(value) || String(value)}</bdi>;
    return <bdi>{Array.isArray(value) ? value.join('، ') : String(value)}</bdi>;
  }

  return (
    <div className="fl-viewlayout">
    <div className="fl-viewlayout__main fl-stack">
      {back}
      <PageHeader title={formType.label} actions={actions?.(request)}>
        <div className="fl-row fl-small fl-muted">
          <span>رقم الطلب:</span><strong data-fl-num>{request.id}</strong>
          <StatusBadge status={request.status} />
          {request.revision > 1 && <span>· النسخة {request.revision}</span>}
          {ownerName && <span>· <bdi>{ownerName}</bdi></span>}
          {request.submitted_at && <span>· أُرسل <bdi dir="ltr">{formatDate(request.submitted_at)}</bdi></span>}
        </div>
      </PageHeader>
      <Summary request={request} />
      {request.status === 'returned' && request.returned_reason && (
        <Alert tone="warning" title="أُعيد الطلب للتعديل">{request.returned_reason}</Alert>
      )}
      {formType.sections.map((section) => {
        const rows = section.fields.map((spec) => [spec, display(spec)]).filter(([, shown]) => shown);
        if (!rows.length) return null;
        return (
          <Card key={section.title} title={section.title}>
            <dl className="fl-dl">
              {rows.map(([spec, shown]) => (
                <div key={spec.name}><dt>{spec.label}</dt><dd>{shown}</dd></div>
              ))}
            </dl>
          </Card>
        );
      })}
      {review && <ReviewActions request={request} own={review.own(request)} daftraNote={formType.daftra_note} onDone={review.onDone} />}
    </div>
    {/* Beside the sections on a wide screen, under them on a narrow one */}
    <div className="fl-viewlayout__side fl-stack">
      {formType.invoiced && <DaftraCard request={request} />}
      {events.length > 0 && <History events={events} />}
    </div>
    </div>
  );
}
