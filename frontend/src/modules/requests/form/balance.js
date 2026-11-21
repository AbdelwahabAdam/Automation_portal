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
// null with no client; else { status: 'loading' | 'error' | 'ready', lines: [[key, label, amount], …] }.
// Both lines always come — the block stands with the client's note from the moment they are found,
// and does not move when Daftra answers. An amount is null while Daftra has not answered, when it
// could not, or when it would not say («غير متاح»); 0 is a figure like any other, so the
// salesperson sees that it was checked.
export function balanceView(info) {
  if (!info) return null;
  const status = ['loading', 'ready'].includes(info.status) ? info.status : 'error';
  const known = status === 'ready' ? info.balance : null;
  return {
    status,
    lines: [
      ['owed', 'المستحق عليه', amountOf(known?.owed)],
      ['credit', 'رصيد دائن', amountOf(known?.credit)],
    ],
  };
}

// What the client holds with us, for the form's «رصيد سابق»: the credit when there is some, else
// null — also while Daftra has not answered, failed, or would not say
export function clientCredit(info) {
  const credit = info?.status === 'ready' ? amountOf(info.balance?.credit) : null;
  return credit > 0 ? credit : null;
}
