// The client's balance in Daftra, as the form shows it once a client is found: what they still owe
// on their invoices, and what they hold with us (رصيد دائن, الدائن on their page in Daftra).

// A figure Daftra gave, or null when it did not: a credit it could not work out arrives as null
// (clients.in_daftra.balance), and an older answer may have no balance in it at all
function amountOf(value) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

// What the «رصيد العميل في دفترة» block shows for the found client (info: the form's clientInfo):
// null with no client; { status: 'loading' } or { status: 'error' } while Daftra has not answered
// or could not; else { status: 'ready', lines: [[key, label, amount], …] }. Both lines always come,
// 0 included, so the salesperson sees that it was checked; an amount of null reads «غير متاح».
export function balanceView(info) {
  if (!info) return null;
  if (info.status === 'loading') return { status: 'loading' };
  if (info.status !== 'ready') return { status: 'error' };
  return {
    status: 'ready',
    lines: [
      ['owed', 'المستحق عليه', amountOf(info.balance?.owed)],
      ['credit', 'رصيد دائن', amountOf(info.balance?.credit)],
    ],
  };
}

// What the client holds with us, for the form's «رصيد سابق»: the credit when there is some, else
// null — also while Daftra has not answered, failed, or would not say
export function clientCredit(info) {
  const credit = info?.status === 'ready' ? amountOf(info.balance?.credit) : null;
  return credit > 0 ? credit : null;
}
