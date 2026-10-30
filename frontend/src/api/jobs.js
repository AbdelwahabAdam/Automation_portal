// The «المزامنة مع دفترة» page: how the last runs went, and starting another.
import { api } from './http.js';

export const syncStatus = () => api('/admin/daftra-sync');
export const startSync = (kinds) => api('/admin/daftra-sync', { method: 'POST', body: { kinds } });
