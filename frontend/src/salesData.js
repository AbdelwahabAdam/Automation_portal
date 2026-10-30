import { useEffect, useState } from 'react';
import { api } from './api.js';

// What the sales pages need from the server, loaded once for users who have them:
// the form definitions, our product catalog, the Daftra staff names and the Daftra lists
// some fields pick from. A list that could not be loaded stays null (or out of daftraLists),
// with its error where the forms can say why.
export function useSalesData(enabled) {
  const [sales, setSales] = useState({
    formTypes: null, error: '', products: null, productsError: '', catalogItems: null, catalogItemsError: '', staff: [],
    // Daftra lists some fields pick from, by field type
    daftraLists: {},
  });

  useEffect(() => {
    if (!enabled) return;
    const update = (changes) => setSales((current) => ({ ...current, ...changes }));
    const addList = (type, rows) => setSales((current) => ({ ...current, daftraLists: { ...current.daftraLists, [type]: rows } }));
    api('/form-types').then((formTypes) => update({ formTypes })).catch((err) => update({ error: err.message }));
    api('/products').then((products) => update({ products })).catch((err) => update({ productsError: err.message }));
    api('/catalog/picker').then((catalogItems) => update({ catalogItems })).catch((err) => update({ catalogItemsError: err.message }));
    api('/daftra/staff').then((staff) => update({ staff })).catch(() => {});
    api('/daftra/treasuries').then((rows) => addList('daftra_treasury', rows)).catch(() => {});
    api('/daftra/order_sources').then((rows) => addList('daftra_order_source', rows)).catch(() => {});
    api('/daftra/client_categories').then((rows) => addList('daftra_client_category', rows)).catch(() => {});
    api('/daftra/staff_members').then((rows) => addList('daftra_staff', rows)).catch(() => {});
  }, [enabled]);

  return sales;
}
