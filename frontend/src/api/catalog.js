// The products and packages: what the forms pick from, and the admin page that keeps them.
import { api } from './http.js';

export const productsForForms = () => api('/products');
export const picker = () => api('/catalog/picker');

export const listProducts = () => api('/admin/products');
export const createProduct = (body) => api('/admin/products', { method: 'POST', body });
export const updateProduct = (id, body) => api(`/admin/products/${id}`, { method: 'PUT', body });
export const deleteProduct = (id) => api(`/admin/products/${id}`, { method: 'DELETE' });

export const listPackages = () => api('/admin/packages');
export const createPackage = (body) => api('/admin/packages', { method: 'POST', body });
export const updatePackage = (id, body) => api(`/admin/packages/${id}`, { method: 'PUT', body });
export const deletePackage = (id) => api(`/admin/packages/${id}`, { method: 'DELETE' });
