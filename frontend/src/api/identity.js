// Logging in, the account page, and the users and roles screens.
// The paths live here and nowhere else.
import { api } from './http.js';

export const me = () => api('/auth/me');
export const logIn = (username, password, code = '') =>
  api('/auth/login', { method: 'POST', body: { username, password, code } });
export const logOut = () => api('/auth/logout', { method: 'POST' });
export const forgotPassword = (username) => api('/auth/forgot-password', { method: 'POST', body: { username } });
export const whosePasswordLink = (token) => api(`/auth/password-link?${new URLSearchParams({ token })}`);
export const setPassword = (token, password) => api('/auth/set-password', { method: 'POST', body: { token, password } });

export const myAccount = () => api('/account');
export const renameMe = (fullName) => api('/account', { method: 'PUT', body: { full_name: fullName } });
export const changeMyPassword = (current, next) =>
  api('/account/password', { method: 'POST', body: { current_password: current, new_password: next } });
export const sendTwoStepCode = () => api('/account/mfa/send-code', { method: 'POST' });
export const enableTwoStep = (code) => api('/account/mfa/enable', { method: 'POST', body: { code } });
export const disableTwoStep = (password) => api('/account/mfa/disable', { method: 'POST', body: { password } });

export const listUsers = () => api('/admin/users');
export const createUser = (body) => api('/admin/users', { method: 'POST', body });
export const updateUser = (id, body) => api(`/admin/users/${id}`, { method: 'PUT', body });
export const deleteUser = (id) => api(`/admin/users/${id}`, { method: 'DELETE' });
export const inviteUser = (id) => api(`/admin/users/${id}/invite`, { method: 'POST' });
export const resetUserTwoStep = (id) => api(`/admin/users/${id}/mfa-reset`, { method: 'POST' });
export const daftraStaffForLinking = () => api('/admin/daftra/staff');

export const listRoles = () => api('/admin/roles');
export const createRole = (body) => api('/admin/roles', { method: 'POST', body });
export const updateRole = (id, body) => api(`/admin/roles/${id}`, { method: 'PUT', body });
export const deleteRole = (id) => api(`/admin/roles/${id}`, { method: 'DELETE' });
// The two tabs of الأدوار والصلاحيات: a row per form with its three keys, and the admin pages
export const assignablePermissions = () => api('/admin/permissions');
