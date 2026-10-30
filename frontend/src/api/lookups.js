// Daftra's own lists, and the «مصادر الطلب» page.
import { api } from './http.js';

export const staff = () => api('/daftra/staff');
// With their ids, for a field holding the staff member and not just their name (الفني)
export const staffMembers = () => api('/daftra/staff_members');
export const treasuries = () => api('/daftra/treasuries');
export const orderSources = () => api('/daftra/order_sources');

export const listOrderSources = () => api('/admin/order-sources');
export const addOrderSource = (name) => api('/admin/order-sources', { method: 'POST', body: { name } });
export const setOrderSourceActive = (id, active) =>
  api(`/admin/order-sources/${id}`, { method: 'PUT', body: { active } });
