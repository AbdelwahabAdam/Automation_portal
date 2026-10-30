// The activity log and its export.
import { api, downloadFile } from './http.js';

export const options = () => api('/admin/audit/options');
export const page = (query) => api(`/admin/audit?${query}`);
export const exportCsv = (query, filename = 'audit-log.csv') =>
  downloadFile(`/admin/audit/export?${query}`, filename);
