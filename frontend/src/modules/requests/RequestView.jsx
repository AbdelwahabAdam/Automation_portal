import { Fragment, useEffect, useState } from 'react';
import { canShareFiles, openAttachment, prepareShare, shareAttachment } from '../../api/http.js';
import * as requestsApi from '../../api/requests.js';
import * as reviewApi from '../../api/review.js';
import { FileRow } from './attachments.jsx';
import {
  ActionBar, Alert, Badge, Button, Card, Dialog, Field, Icon, Loading, PageHeader, StatusBadge, TextArea,
  useToast,
} from '../../ds/index.jsx';
import { formatAmount, formatDate, formatDay, formatMoney } from '../../lib/format.js';
import { DAFTRA_LIST_TYPES, groupLines } from './validation.js';

// The PDFs approving a request saves on it (see backend/app/modules/invoicing/)
const DAFTRA_PDFS = [['daftra_estimate', 'عرض السعر PDF'], ['daftra_invoice', 'الفاتورة PDF'],
  ['daftra_receipt', 'سند القبض PDF'], ['daftra_work_order', 'أمر الشغل PDF']];

// What needs the width of a phone to itself: everything else reads as a label beside its value
const STACKED_TYPES = ['order_lines', 'files', 'textarea', 'multiselect'];

// One of the documents Daftra made: open it, or hand it to another app — WhatsApp, Mail, Drive.
// Where the browser cannot share a file (plain HTTP, and most computers) it is saved instead, and
// the toast says so; the file is then sent from any app by hand.
function DocRow({ label, file }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  // Loaded before the tap: Safari stops counting the tap as the user's own across an await, and
  // then refuses to share. Only worth doing where sharing is possible at all.
  useEffect(() => {
    if (canShareFiles()) prepareShare(file.id, file.filename);
  }, [file.id, file.filename]);

  async function share() {
    setBusy(true);
    try {
      if (await shareAttachment(file.id, file.filename, label) === 'downloaded') {
        toast('تم تنزيل الملف لإرساله من أي تطبيق.');
      }
    } catch (err) {
      toast(err.message, 'error');
    }
    setBusy(false);
  }

  return (
    <div className="fl-dl__stacked">
      <dt>{label}</dt>
      <dd className="fl-row fl-doc">
        <button type="button" className="fl-link fl-row" onClick={() => openAttachment(file.id)}>
          <Icon name="file-text" size={16} /><bdi>{file.filename}</bdi>
        </button>
        <Button
          size="sm" variant="ghost" icon={busy ? 'loader' : 'share'} iconOnly disabled={busy}
          label={`مشاركة ${label}`} onClick={share}
        />
      </dd>
    </div>
  );
}

// What approving the request created in Daftra, or why it could not be created
function DaftraCard({ request }) {
  const pdfs = DAFTRA_PDFS
    .map(([field, label]) => [label, request.attachments.find((a) => a.field === field)])
    .filter(([, file]) => file);
  if (!request.daftra_invoice_no && !request.daftra_estimate_no && !request.daftra_error) return null;
  return (
    <Card title="دفترة">
      {request.daftra_error && (
        <Alert tone="error" title="تعذر إكمال الإنشاء في دفترة">
          {request.daftra_error}
          {request.status === 'submitted' && <p>بعد حل المشكلة اعتمد الطلب مرة أخرى؛ يُكمل من حيث توقف ولا يكرر ما أُنشئ.</p>}
        </Alert>
      )}
      <dl className="fl-dl">
        {request.daftra_estimate_no && <div><dt>رقم عرض السعر</dt><dd><bdi dir="ltr">{request.daftra_estimate_no}</bdi></dd></div>}
        {request.daftra_invoice_no && <div><dt>رقم الفاتورة</dt><dd><bdi dir="ltr">{request.daftra_invoice_no}</bdi></dd></div>}
        {request.daftra_receipt_no && <div><dt>رقم سند القبض</dt><dd><bdi dir="ltr">{request.daftra_receipt_no}</bdi></dd></div>}
        {request.daftra_work_order_no && <div><dt>رقم أمر الشغل</dt><dd><bdi dir="ltr">{request.daftra_work_order_no}</bdi></dd></div>}
        {pdfs.map(([label, file]) => <DocRow key={file.id} label={label} file={file} />)}
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
    // Asked only for a new client, and sent to Daftra when it is created
    ['نوع العميل', data.customer_type],
    ['الجنس', data.gender],
    ['البريد الإلكتروني', data.email && <bdi dir="ltr">{data.email}</bdi>],
  ].filter(([, value]) => value);
  const money = SUMMARY_MONEY.filter(([name]) => typeof data[name] === 'number');
  const daftra = [
    ['عرض السعر', request.daftra_estimate_no], ['الفاتورة', request.daftra_invoice_no],
    ['سند القبض', request.daftra_receipt_no], ['أمر الشغل', request.daftra_work_order_no],
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
// daftraNote: what approving creates in Daftra, from the form's definition (backend/app/forms/<key>/__init__.py "daftra_note")
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
      await reviewApi.decide(request.id, kind, body);
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
export default function RequestView({ requestId, formTypes, onBack, ownerName: given, review, actions }) {
  const [request, setRequest] = useState(null);
  // Whose it is, shown to whoever is reviewing it rather than to its own owner
  const ownerName = given ?? (review && request ? request.created_by_name : null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([requestsApi.getRequest(requestId), requestsApi.requestHistory(requestId)])
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
      // The same table the form shows, without the boxes: each number under its own heading
      const amount = (value) => (typeof value === 'number' ? <bdi dir="ltr">{formatMoney(value)}</bdi> : '—');
      return (
        <div className="fl-table-wrap fl-order-lines">
          <div className="fl-table-scroll">
            <table className="fl-table">
              <thead>
                <tr><th>المنتج</th><th>الكمية</th><th>سعر الوحدة (درهم)</th><th>الإجمالي (درهم)</th></tr>
              </thead>
              <tbody>
                {groupLines(lines).map((group) => {
                  const first = group.rows[0].line;
                  // The details describe the package (or the one standalone product) as a whole, not each item inside it
                  const details = lineFields
                    .map((dspec) => [dspec.label, first.details?.[dspec.name]])
                    .filter(([, v]) => v != null && v !== '');
                  const total = group.rows.reduce((sum, { line }) => sum + (line.unit_price || 0) * (Number(line.quantity) || 0), 0);
                  return (
                    <Fragment key={group.key}>
                      {group.groupName && (
                        <tr className="fl-row--group">
                          <td className="fl-cell--wrap fl-cell--title">
                            <bdi><strong>{group.groupName}</strong></bdi>
                            <span className="fl-cell__sub">باقة — <span data-fl-num>{group.rows.length}</span> منتجات</span>
                          </td>
                          <td className="fl-cell--qty" data-label="عدد الباقات" data-fl-num>{Number(first.details?.package_quantity) || 1}</td>
                          <td className="fl-cell--unit fl-muted" data-label="سعر الوحدة">—</td>
                          <td className="fl-cell--total" data-label="الإجمالي" data-fl-num><strong>{amount(total)}</strong></td>
                        </tr>
                      )}
                      {group.rows.map(({ line, index }) => (
                        <tr key={index} className={group.groupName ? 'fl-row--child' : undefined}>
                          <td className="fl-cell--wrap fl-cell--title"><bdi>{line.name}</bdi></td>
                          <td className="fl-cell--qty" data-label="الكمية" data-fl-num>{line.quantity}</td>
                          <td className="fl-cell--unit" data-label="سعر الوحدة" data-fl-num>{amount(line.unit_price)}</td>
                          <td className="fl-cell--total" data-label="الإجمالي" data-fl-num>
                            {amount(typeof line.unit_price === 'number' ? line.unit_price * (Number(line.quantity) || 0) : undefined)}
                          </td>
                        </tr>
                      ))}
                      {details.length > 0 && (
                        <tr className="fl-row--detail">
                          <td colSpan={4}>
                            <dl className="fl-dl">
                              {details.map(([label, v]) => <div key={label}><dt>{label}</dt><dd><bdi>{v}</bdi></dd></div>)}
                            </dl>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
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
    // A number with its unit, e.g. مدة التركيب: «20 يومًا»
    if (spec.unit && typeof value === 'number') return `${value} ${spec.unit}`;
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
      {request.status === 'draft' && ownerName && (
        <Alert tone="info" title="مسودة لم تُرسل بعد">
          آخر حفظ <bdi dir="ltr">{formatDate(request.updated_at)}</bdi>. للعرض فقط؛ يكملها الموظف ويرسلها من «طلباتي».
        </Alert>
      )}
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
                <div key={spec.name} className={STACKED_TYPES.includes(spec.type) ? 'fl-dl__stacked' : undefined}>
                  <dt>{spec.label}</dt><dd>{shown}</dd>
                </div>
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
