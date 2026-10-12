import test, { afterEach, after } from 'node:test';
import assert from 'node:assert/strict';
import axios from 'axios';
import { tsModuleUrl } from './load-ts.mjs';

const redirects = [];
const fakeWindow = new EventTarget();
fakeWindow.location = { pathname: '/admin', search: '?page=2', hash: '#jobs', replace: url => redirects.push(url) };
const fakeDocument = new EventTarget();
fakeDocument.visibilityState = 'visible';
class FakeChannel {
  static instance;
  constructor() { FakeChannel.instance = this; }
  postMessage() {}
  receive() { this.onmessage?.({ data: 'changed' }); }
}
const originals = { window: globalThis.window, document: globalThis.document, BroadcastChannel: globalThis.BroadcastChannel };
Object.assign(globalThis, { window: fakeWindow, document: fakeDocument, BroadcastChannel: FakeChannel });

const { apiClient } = await import(await tsModuleUrl(new URL('../src/lib/apiClient.ts', import.meta.url)));
const { queryClient } = await import(await tsModuleUrl(new URL('../src/lib/queryClient.ts', import.meta.url)));
const { getAccount, login, logout, startSessionSync } = await import(await tsModuleUrl(new URL('../src/services/auth.ts', import.meta.url)));
const { loginErrorMessage } = await import(await tsModuleUrl(new URL('../src/lib/authErrors.ts', import.meta.url)));

let cookie = null;
let serial = 0;
let lifetime = 600;
let calls = [];
let writes = 0;
const response = (config, data, status = 200, headers = {}) => ({ config, data, status, headers, statusText: '' });
function reject(config, status, headers = {}) {
  throw new axios.AxiosError('Request rejected', undefined, config, {}, response(config, {}, status, headers));
}
function current() { return { id: 1, username: 'admin', role: 'admin', csrf_token: cookie, expires_in: lifetime, has_source_profile: true }; }
function server(config) {
  calls.push(config.url);
  if (config.url === '/api/v1/auth/login') { cookie = `session-${++serial}`; return response(config, current()); }
  if (!cookie) return reject(config, 401);
  if (config.url === '/api/v1/auth/me') return response(config, current());
  if (config.method !== 'get' && config.headers.get('X-CSRF-Token') !== cookie) {
    return reject(config, 403, { 'x-auth-error': 'csrf_invalid' });
  }
  if (config.url === '/api/v1/auth/logout') cookie = null;
  else if (config.method === 'post') writes++;
  return response(config, { ok: true });
}
const adapter = async config => server(config);
apiClient.defaults.adapter = adapter;
startSessionSync();
const flush = async () => { for (let i = 0; i < 5; i++) await new Promise(resolve => setImmediate(resolve)); };

afterEach(async () => {
  apiClient.defaults.adapter = adapter;
  await logout();
  queryClient.clear();
  lifetime = 600;
  calls = [];
  writes = 0;
  redirects.length = 0;
});
after(() => { Object.assign(globalThis, originals); });

test('login distinguishes credentials, forbidden, validation, server, network and timeout failures', () => {
  const error = (status, headers = {}) => new axios.AxiosError('failed', undefined, {}, {}, response({}, {}, status, headers));
  assert.match(loginErrorMessage(error(401)), /mật khẩu không đúng/);
  assert.match(loginErrorMessage(error(403)), /bị từ chối/);
  assert.match(loginErrorMessage(error(422)), /không hợp lệ/);
  for (const status of [500, 502, 503, 504]) assert.match(loginErrorMessage(error(status)), /tạm thời không khả dụng/);
  assert.match(loginErrorMessage(new axios.AxiosError('offline', 'ERR_NETWORK')), /kết nối mạng/);
  assert.match(loginErrorMessage(new axios.AxiosError('slow', 'ECONNABORTED')), /phản hồi quá lâu/);
  assert.match(loginErrorMessage(error(429, { 'retry-after': '23' })), /23 giây/);
  assert.match(loginErrorMessage(error(429)), /15 phút/);
  assert.doesNotMatch(loginErrorMessage(new Error('unexpected')), /mật khẩu không đúng/);
});

test('parallel account reads share one request', async () => {
  await login('admin', 'test-only-password'); calls = [];
  await Promise.all([getAccount(), getAccount(), getAccount()]);
  assert.deepEqual(calls, ['/api/v1/auth/me']);
});

test('login in another tab refreshes CSRF before the next write', async () => {
  await login('admin', 'test-only-password');
  cookie = 'other-tab-session';
  FakeChannel.instance.receive(); await flush();
  await apiClient.post('/api/v1/test-write');
  assert.equal(writes, 1);
  assert.equal(calls.filter(url => url === '/api/v1/test-write').length, 1);
});

test('a missed tab event recovers an explicitly rejected CSRF request once', async () => {
  await login('admin', 'test-only-password');
  cookie = 'rotated-before-write';
  await apiClient.post('/api/v1/test-write');
  assert.equal(writes, 1);
  assert.equal(calls.filter(url => url === '/api/v1/test-write').length, 2);
  assert.equal(redirects.length, 0);
});

test('persistent CSRF rejection is not retried more than once', async () => {
  await login('admin', 'test-only-password');
  let attempts = 0;
  apiClient.defaults.adapter = async config => {
    if (config.url === '/api/v1/test-write') { attempts++; return reject(config, 403, { 'x-auth-error': 'csrf_invalid' }); }
    return server(config);
  };
  await assert.rejects(apiClient.post('/api/v1/test-write'), error => error.response.status === 403);
  assert.equal(attempts, 2);
});

test('ordinary forbidden responses neither retry writes nor end the session', async () => {
  await login('admin', 'test-only-password');
  let attempts = 0;
  apiClient.defaults.adapter = async config => {
    if (config.url === '/api/v1/test-write') { attempts++; return reject(config, 403); }
    return server(config);
  };
  await assert.rejects(apiClient.post('/api/v1/test-write'));
  assert.equal(attempts, 1);
  assert.equal(redirects.length, 0);
});

test('401 from a data API clears cached data and preserves the full return URL', async () => {
  await login('admin', 'test-only-password');
  queryClient.setQueryData(['private-data'], ['cached']);
  cookie = null;
  await assert.rejects(apiClient.get('/api/v1/admin/auto-tag/status'));
  assert.equal(queryClient.getQueryCache().getAll().length, 0);
  assert.equal(redirects.length, 1);
  const target = new URL(redirects[0], 'http://localhost');
  assert.equal(target.searchParams.get('next'), '/admin?page=2#jobs');
  assert.equal(target.searchParams.get('reason'), 'session-expired');
});

test('logout in another tab removes the stale session UI', async () => {
  await login('admin', 'test-only-password'); cookie = null;
  FakeChannel.instance.receive(); await flush();
  assert.equal(redirects.length, 1);
});

test('returning to a tab checks a revoked session', async () => {
  await login('admin', 'test-only-password'); cookie = null;
  fakeWindow.dispatchEvent(new Event('focus')); await flush();
  assert.equal(redirects.length, 1);
});

test('an idle page checks the server at its session deadline', async () => {
  lifetime = 0;
  await login('admin', 'test-only-password'); cookie = null;
  await new Promise(resolve => setTimeout(resolve, 1_100));
  assert.equal(redirects.length, 1);
});

test('a late 401 from the old session does not invalidate a newer login', async () => {
  await login('admin', 'test-only-password');
  let release;
  apiClient.defaults.adapter = config => config.url === '/api/v1/slow'
    ? new Promise((_, rejectPromise) => { release = () => { try { reject(config, 401); } catch (error) { rejectPromise(error); } }; })
    : adapter(config);
  const old = apiClient.get('/api/v1/slow');
  const rejected = assert.rejects(old);
  await flush();
  await login('admin', 'test-only-password');
  release(); await rejected;
  assert.equal(redirects.length, 0);
  assert.equal((await getAccount()).username, 'admin');
});

test('a late account response cannot restore the previous session token', async () => {
  await login('admin', 'test-only-password');
  let release;
  let firstRead = true;
  apiClient.defaults.adapter = config => {
    if (config.url === '/api/v1/auth/me' && firstRead) {
      firstRead = false;
      const stale = current();
      return new Promise(resolve => { release = () => resolve(response(config, stale)); });
    }
    return adapter(config);
  };
  const pending = getAccount(); await flush();
  const newer = await login('admin', 'test-only-password');
  release();
  assert.equal((await pending).csrf_token, newer.csrf_token);
  await apiClient.post('/api/v1/test-write');
  assert.equal(calls.filter(url => url === '/api/v1/test-write').length, 1);
});

test('temporary network failure does not discard a session before its deadline', async () => {
  await login('admin', 'test-only-password');
  queryClient.setQueryData(['private-data'], ['cached']);
  apiClient.defaults.adapter = async config => { throw new axios.AxiosError('offline', 'ERR_NETWORK', config); };
  fakeWindow.dispatchEvent(new Event('focus')); await flush();
  assert.equal(redirects.length, 0);
  assert.deepEqual(queryClient.getQueryData(['private-data']), ['cached']);
});
