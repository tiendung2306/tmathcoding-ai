import axios, { type InternalAxiosRequestConfig } from 'axios';
import { apiClient } from '../lib/apiClient';
import { queryClient } from '../lib/queryClient';

export interface AuthAccount {
  id: number;
  username: string;
  role: 'admin';
  has_source_profile: boolean;
  csrf_token: string;
  expires_in: number;
}

const authTimeout = 15_000;
const syncKey = 'tmath:session-changed';
let account: AuthAccount | null = null;
let generation = 0;
let pendingAccount: Promise<AuthAccount> | null = null;
let checkTimer: ReturnType<typeof setTimeout> | undefined;
let deadline = 0;
let navigating = false;
let channel: BroadcastChannel | undefined;
let syncStarted = false;

interface SessionRequest extends InternalAxiosRequestConfig {
  sessionGeneration?: number;
  csrfRetried?: boolean;
}

function resetSession() {
  invalidateAccountRequest();
  account = null;
  deadline = 0;
  clearTimeout(checkTimer);
}

function invalidateAccountRequest() {
  generation++;
  pendingAccount = null;
}

function loginScreen() {
  return window.location.pathname === '/' || window.location.pathname === '/login';
}

function endSession() {
  resetSession();
  queryClient.clear();
  if (!loginScreen() && !navigating) {
    navigating = true;
    const next = window.location.pathname + window.location.search + window.location.hash;
    window.location.replace(`/?${new URLSearchParams({ reason: 'session-expired', next })}`);
  }
}

function scheduleCheck() {
  clearTimeout(checkTimer);
  if (account) checkTimer = setTimeout(() => { void refreshSession(); }, Math.max(1_000, Math.min(60_000, deadline - Date.now())));
}

function rememberAccount(next: AuthAccount): AuthAccount {
  account = next;
  deadline = Date.now() + next.expires_in * 1_000;
  scheduleCheck();
  return next;
}

export async function getAccount(): Promise<AuthAccount> {
  if (pendingAccount) return pendingAccount;
  const version = generation;
  const request = apiClient.get<AuthAccount>('/api/v1/auth/me', {
    timeout: authTimeout, headers: { 'Cache-Control': 'no-store' },
  }).then(response => version === generation ? rememberAccount(response.data) : getAccount())
    .catch(error => {
      if (version !== generation && account) return getAccount();
      throw error;
    })
    .finally(() => { if (pendingAccount === request) pendingAccount = null; });
  pendingAccount = request;
  return request;
}

async function refreshSession() {
  try { await getAccount(); }
  catch {
    if (account && Date.now() >= deadline) endSession();
    else scheduleCheck();
  }
}

function announceSessionChange() {
  if (channel) channel.postMessage('changed');
  else {
    try { localStorage.setItem(syncKey, `${Date.now()}:${Math.random()}`); }
    catch { /* Focus checks and CSRF recovery also work when browser storage is disabled. */ }
  }
}

export function startSessionSync() {
  if (syncStarted) return;
  syncStarted = true;
  const changed = () => {
    invalidateAccountRequest();
    void refreshSession();
  };
  try {
    channel = new BroadcastChannel(syncKey);
    channel.onmessage = changed;
  } catch {
    window.addEventListener('storage', event => { if (event.key === syncKey) changed(); });
  }
  const resumed = () => { if (!loginScreen() && document.visibilityState === 'visible') void refreshSession(); };
  window.addEventListener('focus', resumed);
  window.addEventListener('pageshow', resumed);
  window.addEventListener('online', resumed);
  document.addEventListener('visibilitychange', resumed);
}

export async function login(username: string, password: string): Promise<AuthAccount> {
  const response = await apiClient.post<AuthAccount>('/api/v1/auth/login', { username, password }, { timeout: authTimeout });
  resetSession();
  navigating = false;
  const authenticated = rememberAccount(response.data);
  announceSessionChange();
  return authenticated;
}

export async function logout(): Promise<void> {
  try { await apiClient.post('/api/v1/auth/logout', undefined, { timeout: authTimeout }); }
  catch (error) {
    if (!(axios.isAxiosError(error) && error.response?.status === 401)) throw error;
  }
  resetSession();
  queryClient.clear();
  announceSessionChange();
}

apiClient.interceptors.request.use(async (config: SessionRequest) => {
  const mutation = !['get', 'head', 'options'].includes(config.method || 'get');
  if (mutation && config.url !== '/api/v1/auth/login') {
    const current = account ?? await getAccount();
    config.headers.set('X-CSRF-Token', current.csrf_token);
  }
  config.sessionGeneration = generation;
  return config;
});

apiClient.interceptors.response.use(response => response, async (error: unknown) => {
  if (!axios.isAxiosError(error)) throw error;
  const config = error.config as SessionRequest | undefined;
  if (!config || config.url === '/api/v1/auth/login') throw error;
  if (error.response?.status === 401) {
    if (config.sessionGeneration === generation && config.url !== '/api/v1/auth/logout') endSession();
  } else if (error.response?.status === 403 && error.response.headers['x-auth-error'] === 'csrf_invalid' && !config.csrfRetried) {
    // This code is returned before the endpoint runs, so one retry cannot repeat a write.
    config.csrfRetried = true;
    invalidateAccountRequest();
    await getAccount();
    return apiClient.request(config);
  }
  throw error;
});
