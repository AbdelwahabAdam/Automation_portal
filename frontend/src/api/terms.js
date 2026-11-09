// الشروط والأحكام: the versioned texts, and the one each package prints.
import { api } from './http.js';

export const listTerms = () => api('/admin/terms');
export const createTerm = (body) => api('/admin/terms', { method: 'POST', body });
export const deleteTerm = (id) => api(`/admin/terms/${id}`, { method: 'DELETE' });

// { package id: term id }; a package missing from it prints no terms
export const packageTerms = () => api('/admin/terms/packages');
// termId null: the package prints no terms
export const setPackageTerm = (packageId, termId) =>
  api(`/admin/terms/packages/${packageId}`, { method: 'PUT', body: { term_id: termId } });
