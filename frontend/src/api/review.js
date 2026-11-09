// The review queue and the two decisions.
import { api } from './http.js';

// scope=review: only the forms the user may decide on, as لوحة المتابعة counted them
export const queue = (scope = '') => api(`/review/requests${scope ? `?scope=${scope}` : ''}`);
export const decide = (id, kind, body) => api(`/review/requests/${id}/${kind}`, { method: 'POST', body });
