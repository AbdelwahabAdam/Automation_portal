// The customers the forms look up, their addresses, and what Daftra says about one.
import { api } from './http.js';

export const lookupClient = (query) => api(`/clients/lookup?${query}`);
export const addClientAddress = (daftraId, address) =>
  api(`/clients/${daftraId}/addresses`, { method: 'POST', body: address });
export const clientInDaftra = (daftraId) => api(`/daftra/clients/${daftraId}`);
export const clientCategories = () => api('/daftra/client_categories');
export const pointOfLink = (url) => api(`/location/from-link?url=${encodeURIComponent(url)}`);
