// The client's balance in Daftra, as the note under a found client reads it: what they still owe
// on their invoices, and what they hold with us (رصيد العميل, الدائن on their page in Daftra).
// Each only when there is some, and nothing at all while Daftra has not answered or would not
// say: a credit it could not work out arrives as null (clients.in_daftra.balance).
export function balanceLines(info) {
  const balance = info?.status === 'ready' ? info.balance : null;
  if (!balance) return [];
  return [
    balance.owed > 0 && ['المستحق عليه', balance.owed],
    balance.credit > 0 && ['رصيد دائن', balance.credit],
  ].filter(Boolean);
}
