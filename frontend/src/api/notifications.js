// The mail test page.
import { api } from './http.js';

export const settings = () => api('/admin/mail');
export const preview = (template) => api(`/admin/mail/preview/${template}`);
export const sendTest = (template, to) => api('/admin/mail/test', { method: 'POST', body: { template, to } });
