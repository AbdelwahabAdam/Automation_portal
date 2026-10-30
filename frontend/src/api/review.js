// The review queue and the two decisions.
import { api } from './http.js';

export const queue = () => api('/review/requests');
export const decide = (id, kind, body) => api(`/review/requests/${id}/${kind}`, { method: 'POST', body });
