// src/api.js with fetch and localStorage stood in for: the messages a failed call shows.
import assert from 'node:assert/strict';
import { test } from 'node:test';

const store = new Map();
globalThis.localStorage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v), removeItem: (k) => store.delete(k) };
globalThis.window = { location: { reload() {} } };
const { api, ApiError } = await import('../src/api.js');

const answer = (status, body) => async () => ({
  ok: status < 400, status, statusText: 'x', json: async () => body,
});

test('the server\'s own message is shown', async () => {
  globalThis.fetch = answer(409, { detail: 'الطلب مُرسل للمراجعة' });
  await assert.rejects(api('/x'), (err) => err instanceof ApiError && err.message === 'الطلب مُرسل للمراجعة' && err.status === 409);
});

test('field errors come back by field', async () => {
  globalThis.fetch = answer(422, { detail: { errors: { phone: 'مطلوب' } } });
  await assert.rejects(api('/x'), (err) => err.fieldErrors.phone === 'مطلوب');
});

test('answers without a message get one in Arabic', async () => {
  globalThis.fetch = answer(422, { detail: [{ loc: ['body'], msg: 'Field required' }] });
  await assert.rejects(api('/x'), (err) => /غير صالحة/.test(err.message));
  globalThis.fetch = answer(500, null);
  await assert.rejects(api('/x'), (err) => /خطأ في الخادم/.test(err.message));
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
  await assert.rejects(api('/x'), (err) => err.status === 0 && /تعذر الاتصال/.test(err.message));
});

test('a 204 answer is null and a token is sent', async () => {
  let sent;
  store.set('portal_token', 'abc');
  globalThis.fetch = async (url, options) => { sent = options; return { ok: true, status: 204 }; };
  assert.equal(await api('/x', { method: 'POST', body: { a: 1 } }), null);
  assert.equal(sent.headers.Authorization, 'Bearer abc');
  assert.equal(sent.body, '{"a":1}');
});
