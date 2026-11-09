// لوحة المتابعة: the five cards and the waiting list, read in one call.
import { api } from './http.js';

export const overview = (params) => {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== '' && value != null));
  return api(`/dashboard?${query}`);
};
