// A salesperson's requests, their files, and the forms they are made from.
import { api, uploadAttachment } from './http.js';

export const formTypes = () => api('/form-types');
export const myRequests = () => api('/requests/mine');
export const myCounts = () => api('/requests/mine/counts');
export const getRequest = (id) => api(`/requests/${id}`);
export const requestHistory = (id) => api(`/requests/${id}/history`);
export const createRequest = (body) => api('/requests', { method: 'POST', body });
export const updateRequest = (id, body) => api(`/requests/${id}`, { method: 'PUT', body });
export const deleteRequest = (id) => api(`/requests/${id}`, { method: 'DELETE' });

export const addAttachment = uploadAttachment;
export const deleteAttachment = (id) => api(`/attachments/${id}`, { method: 'DELETE' });
