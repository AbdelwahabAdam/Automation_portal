// Finding the request's client in our copy of Daftra's client list (by phone or client code),
// filling in their details, choosing one of their addresses, and what Daftra itself knows of them.
import { useRef, useState } from 'react';
import { api } from '../api.js';
import { Alert, Button, Select } from '../ds/index.jsx';
import { coordinatesFromLink, normalizePhone } from '../validation.js';

// Form fields that an existing Daftra client can fill
const CLIENT_FIELDS = ['client_code', 'customer_name', 'phone', 'emirate', 'area', 'street', 'house', 'location_url'];
const ADDRESS_FIELDS = ['emirate', 'area', 'street', 'house', 'location_url'];
// Belongs to the address as much as the fields above: the coordinates come from its link, and
// التصنيف decides its المنطقة and الإمارة. A new address starts without any of them.
const ADDRESS_ALSO = ['coordinates', 'category', 'category_name'];
const BLANK_ADDRESS = Object.fromEntries([...ADDRESS_FIELDS, ...ADDRESS_ALSO].map((name) => [name, '']));
// The fields a client is looked up by
export const SEARCH_FIELDS = ['phone', 'client_code'];

const addressLabel = (address) => [address.emirate, address.area, address.street, address.house].filter(Boolean).join('، ') || 'بلا عنوان مسجل';

// form: { fieldNames, needsClientInfo, setValues, setErrors, setMessage, autoFill, autoFilled } from RequestForm
export function useClientLookup(form) {
  const toast = form.toast;
  // Result of the last search: { field, status: 'loading' | 'found' | 'many' | 'none' | 'error', ... }
  const [lookup, setLookup] = useState(null);
  // id of the found client's address currently filled in, or 'new' while typing one to save
  const [addressChoice, setAddressChoice] = useState(null);
  const [addressBusy, setAddressBusy] = useState(false);
  // The found client as Daftra has them now: { status: 'loading' | 'ready' | 'error', category, open_invoices }
  const [clientInfo, setClientInfo] = useState(null);
  const lastLookup = useRef('');
  // Set while a new address is being typed, so the client's category from Daftra — which may
  // arrive after the user has already asked for a new address — does not fill it back in
  const typingNewAddress = useRef(false);

  async function loadClientInfo(daftraId) {
    setClientInfo({ status: 'loading' });
    try {
      const info = await api(`/daftra/clients/${daftraId}`);
      setClientInfo({ status: 'ready', ...info });
      form.setValues((current) => {
        const next = { ...current };
        // Their current التصنيف, unless one was already picked or a new address is being typed
        if (form.fieldNames.has('category') && info.category && !current.category && !typingNewAddress.current) {
          next.category = String(info.category.id);
          next.category_name = info.category.name;
        }
        // An invoice picked for a different client is dropped
        if (form.fieldNames.has('invoice') && current.invoice && !info.open_invoices.some((i) => String(i.id) === String(current.invoice))) {
          next.invoice = '';
          next.invoice_name = '';
        }
        return next;
      });
    } catch (err) {
      setClientInfo({ status: 'error', message: err.message });
    }
  }

  // What the invoice drop-down says while it has nothing to offer
  function invoicesUnavailable() {
    if (!clientInfo) return 'ابحث عن العميل أولًا برقم الهاتف أو الكود';
    if (clientInfo.status === 'loading') return 'جارٍ تحميل فواتير العميل من دفترة…';
    if (clientInfo.status === 'error') return clientInfo.message;
    if (!clientInfo.open_invoices.length) return 'لا توجد فواتير عليها مبلغ متبقٍ لهذا العميل';
    return null;
  }

  // Fills the client fields that are empty or still hold what a previous search filled in
  function applyClient(client, field) {
    form.setValues((current) => {
      const next = { ...current };
      for (const name of CLIENT_FIELDS) form.autoFill(current, next, name, client[name], name === 'client_code');
      return next;
    });
    form.setErrors((current) => Object.fromEntries(Object.entries(current).filter(([name]) => !CLIENT_FIELDS.includes(name))));
    setLookup({ field, status: 'found', client });
    typingNewAddress.current = false;
    if (form.needsClientInfo) loadClientInfo(client.daftra_id);
    const last = client.addresses?.[client.addresses.length - 1];
    setAddressChoice(last ? String(last.id) : null);
  }

  // Switches the address fields to one of the client's saved addresses, or clears them to type a new one
  function chooseAddress(choice) {
    setAddressChoice(choice);
    typingNewAddress.current = choice === 'new';
    if (choice === 'new') {
      form.setValues((current) => ({ ...current, ...BLANK_ADDRESS }));
      return;
    }
    const address = lookup.client.addresses.find((a) => String(a.id) === choice);
    if (!address) return;
    form.setValues((current) => ({
      ...current,
      ...Object.fromEntries(ADDRESS_FIELDS.map((name) => [name, address[name] ?? ''])),
      // The coordinates of the address being left do not belong to this one
      coordinates: coordinatesFromLink(address.location_url),
    }));
  }

  async function saveNewAddress(values) {
    const { client } = lookup;
    setAddressBusy(true);
    try {
      const address = await api(`/clients/${client.daftra_id}/addresses`, {
        // The coordinates go too: Daftra will not save a client without them
        method: 'POST',
        body: { ...Object.fromEntries(ADDRESS_FIELDS.map((f) => [f, values[f] || ''])), coordinates: values.coordinates || '' },
      });
      setLookup((current) => ({ ...current, client: { ...current.client, addresses: [...current.client.addresses, address] } }));
      setAddressChoice(String(address.id));
      // Never say it reached Daftra when it did not; it is tried again when the request is approved
      toast(address.saved_in_daftra
        ? 'تم حفظ العنوان الجديد لهذا العميل وفي دفترة'
        : 'تم حفظ العنوان هنا، ولم يُحفظ في دفترة الآن — سيُحاول مرة أخرى عند اعتماد الطلب');
    } catch (err) {
      form.setMessage({ error: err.message });
    } finally {
      setAddressBusy(false);
    }
  }

  async function lookupClient(field, raw) {
    const phone = field === 'phone' ? normalizePhone(raw) : null;
    const code = field === 'client_code' && /^[\d٠-٩۰-۹]{1,6}$/.test(raw.trim()) ? raw.trim() : null;
    const query = phone ? `phone=${encodeURIComponent(phone)}` : code ? `code=${encodeURIComponent(code)}` : null;
    if (!query || query === lastLookup.current) return;
    // A code that a search just filled in does not need searching again
    if (field === 'client_code' && raw === form.autoFilled.current.client_code) return;
    lastLookup.current = query;
    setLookup({ field, status: 'loading' });
    try {
      const { matches } = await api(`/clients/lookup?${query}`);
      if (lastLookup.current !== query) return;
      if (matches.length === 1) applyClient(matches[0], field);
      else setLookup({ field, status: matches.length ? 'many' : 'none', matches });
    } catch (err) {
      lastLookup.current = '';
      setLookup({ field, status: 'error', message: err.message });
    }
  }

  // The search icon runs the search again even for the same number, e.g. after a failed attempt
  function searchNow(field, raw) {
    lastLookup.current = '';
    lookupClient(field, String(raw));
  }

  return {
    lookup, addressChoice, addressBusy, clientInfo, invoicesUnavailable, applyClient, chooseAddress, saveNewAddress,
    lookupClient, searchNow,
  };
}

// What the last search found, under the field it was made from
export function ClientLookupNote({ name, client: found, values }) {
  const { lookup, addressChoice, addressBusy } = found;
  if (lookup?.field !== name) return null;
  if (lookup.status === 'loading') return <p className="fl-field__hint">جارٍ البحث عن العميل…</p>;
  if (lookup.status === 'found') {
    const addresses = lookup.client.addresses || [];
    return (
      <Alert tone="success" title="عميل مسجل">
        <p>{lookup.client.customer_name} — كود <bdi dir="ltr">{lookup.client.client_code}</bdi>. تم تعبئة بياناته.</p>
        <div className="fl-row fl-lookup__actions">
          {addresses.length > 0 && (
            <Select value={addressChoice ?? ''} onChange={(e) => found.chooseAddress(e.target.value)} aria-label="عنوان العميل">
              {addresses.map((address) => (
                <option key={address.id} value={String(address.id)}>
                  {addressLabel(address)}{address.is_default ? ' (الأساسي)' : ''}
                </option>
              ))}
              <option value="new">+ عنوان جديد</option>
            </Select>
          )}
          {!addresses.length && addressChoice !== 'new' && (
            <Button type="button" size="sm" variant="tertiary" icon="plus" onClick={() => found.chooseAddress('new')}>
              إضافة عنوان لهذا العميل
            </Button>
          )}
          {addressChoice === 'new' && (
            <Button type="button" size="sm" loading={addressBusy} onClick={() => found.saveNewAddress(values)}>
              حفظ هذا العنوان للعميل
            </Button>
          )}
        </div>
      </Alert>
    );
  }
  if (lookup.status === 'none') {
    return <p className="fl-field__hint">{name === 'phone' ? 'لا يوجد عميل بهذا الرقم (عميل جديد).' : 'لا يوجد عميل بهذا الكود.'}</p>;
  }
  if (lookup.status === 'error') return <Alert tone="warning">{lookup.message}</Alert>;
  return (
    <Alert tone="info" title="يوجد أكثر من عميل بهذا الرقم، اختر العميل">
      <div className="fl-row">
        {lookup.matches.map((client) => (
          <Button key={client.daftra_id} size="sm" onClick={() => found.applyClient(client, name)}>
            {client.customer_name} — <bdi dir="ltr">{client.client_code}</bdi>
          </Button>
        ))}
      </div>
    </Alert>
  );
}
