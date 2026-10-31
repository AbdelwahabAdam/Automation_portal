import { useCallback, useEffect, useState } from 'react';
import * as jobsApi from '../../api/jobs.js';
import { Alert, Badge, Button, Card, Loading, PageHeader } from '../../ds/index.jsx';
import { formatDate, formatMoney } from '../../lib/format.js';

// Refreshes our copies of Daftra's lists (backend/app/daftra_refresh.py): the catalog's linked
// products, and the clients the sales forms look up
const POLL_MS = 2000;

const ABOUT = {
  products: 'يحدّث الاسم والسعر والتفعيل للمنتجات المربوطة بدفترة فقط. لا تُضاف منتجات دفترة الأخرى، ولا يُمسح سعرنا إن لم يكن للمنتج سعر في دفترة.',
  clients: 'يعيد بناء قائمة العملاء والعناوين من دفترة (العملاء الذين لهم رقم هاتف فقط). تعمل تلقائيًا كل ليلة الساعة 11:55.',
};

const STATUS = {
  queued: ['neutral', 'loader', 'في الانتظار'],
  running: ['info', 'loader', 'جارية'],
  done: ['success', 'check-circle', 'تمت'],
  failed: ['error', 'alert-circle', 'فشلت'],
};

function RunStatus({ run }) {
  const [tone, icon, label] = STATUS[run.status] || ['neutral', null, run.status];
  return <Badge tone={tone} icon={icon}>{label}</Badge>;
}

const FIELD_LABELS = { name: 'الاسم', unit_price: 'السعر', is_active: 'مفعّل' };

function showValue(key, value) {
  if (key === 'unit_price') return `${formatMoney(value)} درهم`;
  if (key === 'is_active') return value ? 'نعم' : 'لا';
  return value;
}

// What a products run changed, product by product
function ProductsSummary({ summary }) {
  return (
    <div className="fl-stack fl-stack--sm">
      <p className="fl-flush">
        من <b>{summary.linked}</b> منتجًا مربوطًا بدفترة: تغيّر <b>{summary.changed.length}</b>، وبقي <b>{summary.unchanged}</b> كما هو.
      </p>
      {summary.changed.length > 0 && (
        <div className="fl-table-wrap fl-stacked">
          <div className="fl-table-scroll">
            <table className="fl-table">
              <thead><tr><th>المنتج</th><th>الحقل</th><th>قبل</th><th>بعد</th></tr></thead>
              <tbody>
                {summary.changed.flatMap((item) => Object.keys(item.after).map((key, index) => (
                  <tr key={`${item.id}-${key}`}>
                    <td className="fl-cell--wrap">{index === 0 && <bdi>{item.name}</bdi>}</td>
                    <td className="fl-cell--full" data-label="الحقل">{FIELD_LABELS[key] || key}</td>
                    <td className="fl-cell--wrap" data-label="قبل"><bdi>{showValue(key, item.before[key])}</bdi></td>
                    <td className="fl-cell--wrap" data-label="بعد"><bdi>{showValue(key, item.after[key])}</bdi></td>
                  </tr>
                )))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {summary.missing.length > 0 && (
        <Alert tone="warning" title="منتجات لم تُوجد في دفترة">
          لم تتغير؛ راجع رقم دفترة لكل منها في صفحة المنتجات والباقات:{' '}
          {summary.missing.map((item, index) => (
            <span key={item.id}>{index > 0 && '، '}<bdi>{item.name} (#{item.daftra_id})</bdi></span>
          ))}
        </Alert>
      )}
      {summary.skipped.length > 0 && (
        <Alert tone="warning" title="أسماء لم تُحدَّث">
          {summary.skipped.map((item) => <div key={item.id}><bdi>{item.name}</bdi>: {item.reason}</div>)}
        </Alert>
      )}
    </div>
  );
}

function ClientsSummary({ summary }) {
  return (
    <p className="fl-flush">
      <b>{summary.kept}</b> عميلًا (من <b>{summary.daftra_clients}</b> في دفترة؛ {summary.without_phone} بلا رقم هاتف لم يُحفظوا)،
      مع <b>{summary.addresses}</b> عنوانًا. جديد منذ آخر مزامنة: <b>{summary.added}</b>، ولم يعد في دفترة: <b>{summary.removed}</b>.
    </p>
  );
}

function RunDetails({ run }) {
  return (
    <div className="fl-stack fl-stack--sm">
      <div className="fl-row fl-small fl-muted">
        <RunStatus run={run} />
        <span>بواسطة <bdi>{run.started_by || '—'}</bdi></span>
        <span>· <bdi dir="ltr">{formatDate(run.finished_at || run.started_at)}</bdi></span>
      </div>
      {run.status === 'failed' && <Alert tone="error" title="تعذرت المزامنة">{run.error}</Alert>}
      {run.status === 'done' && run.summary && (
        run.kind === 'products' ? <ProductsSummary summary={run.summary} /> : <ClientsSummary summary={run.summary} />
      )}
    </div>
  );
}

export default function DaftraSync() {
  const [state, setState] = useState(null);
  const [error, setError] = useState('');
  const [starting, setStarting] = useState('');

  const load = useCallback(() => jobsApi.syncStatus().then(setState).catch((err) => setError(err.message)), []);
  useEffect(() => { load(); }, [load]);

  const busy = Boolean(state?.kinds.some((kind) => kind.busy));
  // While a sync runs, the page follows it until it ends
  useEffect(() => {
    if (!busy) return undefined;
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [busy, load]);

  async function start(kinds, key) {
    setStarting(key);
    setError('');
    try {
      await jobsApi.startSync(kinds);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setStarting('');
    }
  }

  const header = (
    <PageHeader
      title="المزامنة مع دفترة"
      subtitle="جلب آخر بيانات المنتجات والعملاء من دفترة إلى البوابة"
      actions={state && (
        <Button variant="primary" icon="refresh" loading={starting === 'all'} disabled={busy || Boolean(starting)}
          onClick={() => start(state.kinds.map((kind) => kind.key), 'all')}>
          مزامنة الكل
        </Button>
      )}
    />
  );
  if (!state) return <div className="fl-stack">{header}{error ? <Alert tone="error">{error}</Alert> : <Loading />}</div>;

  return (
    <div className="fl-stack">
      {header}
      {error && <Alert tone="error">{error}</Alert>}
      {busy && <Alert tone="info">المزامنة جارية، وتُحدَّث هذه الصفحة تلقائيًا حتى تنتهي. يمكنك مغادرتها؛ تكمل المزامنة في الخادم.</Alert>}
      {state.kinds.map((kind) => (
        <Card
          key={kind.key}
          title={kind.label}
          actions={(
            <Button icon="refresh" size="sm" loading={starting === kind.key} disabled={busy || Boolean(starting)}
              onClick={() => start([kind.key], kind.key)}>
              مزامنة {kind.label}
            </Button>
          )}
        >
          <div className="fl-stack fl-stack--sm">
            <p className="fl-muted fl-small fl-flush">{ABOUT[kind.key]}</p>
            {kind.key === 'products' && !state.has_linked_products && (
              <Alert tone="warning">لا يوجد منتج مربوط بدفترة بعد؛ اربط المنتجات برقم دفترة من صفحة المنتجات والباقات.</Alert>
            )}
            {kind.busy && <RunDetails run={kind.busy} />}
            {!kind.busy && (kind.last ? <RunDetails run={kind.last} /> : <p className="fl-muted fl-flush">لم تتم مزامنة بعد.</p>)}
          </div>
        </Card>
      ))}
      {state.history.length > 0 && (
        <Card title="آخر المزامنات">
          <div className="fl-table-wrap fl-stacked">
            <div className="fl-table-scroll">
              <table className="fl-table">
                <thead><tr><th>القائمة</th><th>الحالة</th><th>بواسطة</th><th>البداية</th><th>النهاية</th></tr></thead>
                <tbody>
                  {state.history.map((run) => (
                    <tr key={run.id}>
                      <td>{run.label}</td>
                      <td data-label="الحالة"><RunStatus run={run} /></td>
                      <td data-label="بواسطة"><bdi>{run.started_by || '—'}</bdi></td>
                      <td data-label="البداية"><bdi dir="ltr">{formatDate(run.started_at)}</bdi></td>
                      <td data-label="النهاية"><bdi dir="ltr">{run.finished_at ? formatDate(run.finished_at) : '—'}</bdi></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
