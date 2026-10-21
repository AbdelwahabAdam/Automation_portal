// A page of requests: a table on a wide area, cards on a narrow one (same data, same actions).
// Used by «طلباتي» and «المراجعة», which differ only in their columns and actions.
import { Pager, StatusBadge } from './ds/index.jsx';
import { formatDate } from './formsMeta.js';

// Table on a wide area, cards on a narrow one
export const TABLE_MIN_WIDTH = 760;

// Why a returned request came back, under its row
const returnNote = (r) => r.status === 'returned' && r.returned_reason && <span className="fl-rownote">سبب الإعادة: {r.returned_reason}</span>;

// Each column a list can show: its heading, its cell in the table, and its line on a card (null: not on cards)
const COLUMNS = {
  id: { label: 'رقم الطلب', className: 'fl-cell--id', num: true, cell: (r) => r.id, card: (r) => r.id },
  type: { label: 'نوع النموذج', className: 'fl-cell--wrap', cell: (r, ctx) => ctx.labels[r.form_type] || r.form_type, card: null },
  client: {
    label: 'العميل',
    className: 'fl-cell--wrap',
    cell: (r) => (
      <>
        <bdi>{r.data.customer_name || '—'}</bdi>
        {r.data.phone && <span className="fl-cell__sub"><bdi dir="ltr">{r.data.phone}</bdi></span>}
        {returnNote(r)}
      </>
    ),
    card: (r) => <bdi>{r.data.customer_name || '—'}</bdi>,
  },
  employee: { label: 'الموظف', cell: (r) => <bdi>{r.created_by_name}</bdi>, card: (r) => <bdi>{r.created_by_name}</bdi> },
  status: { label: 'الحالة', cell: (r) => <StatusBadge status={r.status} />, card: null },
  date: {
    label: (ctx) => ctx.dateLabel,
    className: 'fl-cell--nowrap',
    num: true,
    cell: (r, ctx) => <bdi dir="ltr">{formatDate(ctx.dateOf(r))}</bdi>,
    card: (r, ctx) => <bdi dir="ltr">{formatDate(ctx.dateOf(r))}</bdi>,
  },
};

const labelOf = (column, ctx) => (typeof column.label === 'function' ? column.label(ctx) : column.label);

// rows: this page's requests; total: how many there are in all (for the pager)
// columns: keys of COLUMNS in order; dateLabel/dateOf: the date column's heading and value
// actions(r): the buttons of a row; labels: form type key → its name
export default function RequestList({
  rows, total, wide, columns, labels, dateLabel, dateOf, actions, page, pageSize, onPage, onPageSize,
}) {
  const ctx = { labels, dateLabel, dateOf };
  if (wide) {
    return (
      <div className="fl-table-wrap">
        <div className="fl-table-scroll">
          <table className="fl-table">
            <thead>
              <tr>
                {columns.map((key) => <th key={key}>{labelOf(COLUMNS[key], ctx)}</th>)}
                <th>الإجراء</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  {columns.map((key) => (
                    <td key={key} className={COLUMNS[key].className} data-fl-num={COLUMNS[key].num || undefined}>
                      {COLUMNS[key].cell(r, ctx)}
                    </td>
                  ))}
                  <td className="fl-cell--actions">{actions(r)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pager page={page} pageSize={pageSize} total={total} onPage={onPage} onPageSize={onPageSize} />
      </div>
    );
  }
  const cardColumns = columns.filter((key) => COLUMNS[key].card);
  return (
    <>
      <ul className="fl-cards" role="list">
        {rows.map((r) => (
          <li key={r.id} className="fl-rowcard">
            <div className="fl-rowcard__head">
              <span className="fl-rowcard__title">{labels[r.form_type] || r.form_type}</span>
              <StatusBadge status={r.status} />
            </div>
            <dl>
              {cardColumns.map((key) => (
                <div key={key} className="fl-rowcard__item">
                  <dt>{labelOf(COLUMNS[key], ctx)}</dt>
                  <dd data-fl-num={COLUMNS[key].num || undefined}>{COLUMNS[key].card(r, ctx)}</dd>
                </div>
              ))}
            </dl>
            {returnNote(r)}
            <div className="fl-row">{actions(r)}</div>
          </li>
        ))}
      </ul>
      <div className="fl-table-wrap"><Pager page={page} pageSize={pageSize} total={total} onPage={onPage} /></div>
    </>
  );
}
