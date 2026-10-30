const TOKEN_KEY = 'portal_token';

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token) => (token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY));

// What to tell the user when the server's answer carries no message of its own
function messageFor(status, detail) {
  if (typeof detail === 'string' && detail) return detail;
  // FastAPI's own check of the request's shape (a list of problems, in English)
  if (status === 422 && Array.isArray(detail)) return 'بعض البيانات المرسلة غير صالحة. حدّث الصفحة وحاول مرة أخرى.';
  if (status >= 500) return 'حدث خطأ في الخادم. حاول مرة أخرى بعد قليل.';
  return 'تعذر تنفيذ الطلب';
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(messageFor(status, detail));
    this.status = status;
    this.fieldErrors = detail?.errors || null;
  }
}

async function request(path, { method = 'GET', body, file } = {}) {
  const token = getToken();
  let res;
  try {
    res = await fetch('/api' + path, {
      method,
      headers: {
        ...(body ? { 'Content-Type': 'application/json' } : {}),
        ...(file ? { 'Content-Type': 'application/octet-stream' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: file || (body ? JSON.stringify(body) : undefined),
    });
  } catch {
    // No answer at all: offline, or the server is down
    throw new ApiError(0, 'تعذر الاتصال بالخادم. تحقق من اتصالك بالإنترنت وحاول مرة أخرى.');
  }
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    // An expired or invalid session sends the user back to the login screen
    if (res.status === 401 && token) {
      setToken(null);
      window.location.reload();
    }
    throw new ApiError(res.status, data?.detail);
  }
  return res;
}

export async function api(path, options) {
  const res = await request(path, options);
  return res.status === 204 ? null : res.json();
}

export function uploadAttachment(requestId, field, file) {
  const query = new URLSearchParams({ field, filename: file.name });
  return api(`/requests/${requestId}/attachments?${query}`, { method: 'POST', file });
}

// A file kept in memory for the browser to show or save; released after a minute, once it has
const blobUrl = (blob) => {
  const url = URL.createObjectURL(blob);
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return url;
};

// A picture of an attachment to show on the page. Kept for as long as the page lives, since the
// same file is shown again as the user scrolls; openAttachment is for opening one, which is one-off.
const shownAttachments = new Map();
export async function attachmentUrl(id) {
  if (!shownAttachments.has(id)) {
    shownAttachments.set(id, (await (await request(`/attachments/${id}`)).blob().then(URL.createObjectURL)));
  }
  return shownAttachments.get(id);
}

// Attachments need the auth header, so they are fetched and opened as a blob
export async function openAttachment(id) {
  const tab = window.open('', '_blank');
  try {
    const url = blobUrl(await (await request(`/attachments/${id}`)).blob());
    if (tab) tab.location = url;
    else window.location = url;
  } catch (err) {
    tab?.close();
    throw err;
  }
}

// The same file, kept so that sharing it is one tap and not a download each time
const fetched = new Map();
async function attachmentFile(id, filename) {
  if (!fetched.has(id)) {
    const blob = await (await request(`/attachments/${id}`)).blob();
    fetched.set(id, new File([blob], filename, { type: blob.type || 'application/octet-stream' }));
  }
  return fetched.get(id);
}

// Whether this device can hand a file to another app at all. The browser only offers it in a secure
// context, so over plain HTTP (today's server) and on most computers the answer is no.
export function canShareFiles() {
  if (!navigator.canShare) return false;
  try {
    return navigator.canShare({ files: [new File(['.'], 'a.pdf', { type: 'application/pdf' })] });
  } catch {
    return false;
  }
}

// Loads the file ahead of the tap, so the share sheet opens without an await in between: Safari
// drops the user's gesture across one and then refuses to share.
export const prepareShare = (id, filename) => attachmentFile(id, filename).catch(() => null);

// Hands a document to whatever the device shares with — WhatsApp, Mail, Drive. Returns what
// happened: 'shared', 'cancelled', or 'downloaded' when the device cannot share files and the
// file was saved instead, to be sent from any app by hand.
export async function shareAttachment(id, filename, title) {
  const file = await attachmentFile(id, filename);
  if (navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: title || filename });
      return 'shared';
    } catch (err) {
      if (err?.name === 'AbortError') return 'cancelled';
      // The sheet refused (no target for it, or the gesture had gone): saving the file still works
    }
  }
  const link = document.createElement('a');
  link.href = blobUrl(file);
  link.download = filename;
  link.click();
  return 'downloaded';
}

// Saves an API response as a file; a plain link cannot send the auth header
export async function downloadFile(path, filename) {
  const link = document.createElement('a');
  link.href = blobUrl(await (await request(path)).blob());
  link.download = filename;
  link.click();
}
