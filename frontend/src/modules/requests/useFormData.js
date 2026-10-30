import { useEffect, useState } from 'react';
import * as catalogApi from '../../api/catalog.js';
import * as clientsApi from '../../api/clients.js';
import * as lookupsApi from '../../api/lookups.js';
import * as requestsApi from '../../api/requests.js';

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
    requestsApi.formTypes().then((formTypes) => update({ formTypes })).catch((err) => update({ error: err.message }));
    catalogApi.productsForForms().then((products) => update({ products })).catch((err) => update({ productsError: err.message }));
    catalogApi.picker().then((catalogItems) => update({ catalogItems })).catch((err) => update({ catalogItemsError: err.message }));
    lookupsApi.staff().then((staff) => update({ staff })).catch(() => {});
    lookupsApi.treasuries().then((rows) => addList('daftra_treasury', rows)).catch(() => {});
    lookupsApi.orderSources().then((rows) => addList('daftra_order_source', rows)).catch(() => {});
    clientsApi.clientCategories().then((rows) => addList('daftra_client_category', rows)).catch(() => {});
    lookupsApi.staffMembers().then((rows) => addList('daftra_staff', rows)).catch(() => {});
  }, [enabled]);

  return sales;
}
