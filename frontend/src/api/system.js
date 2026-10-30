// Which version of the portal is answering.
import { api } from './http.js';

export const version = () => api('/admin/version');
