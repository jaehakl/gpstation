import { API_URL, request } from './http';
import type {
  AccessKeyCreate,
  AccessKeyCreateResult,
  AccessKeyData,
  DashboardSummary,
  LauncherSessionView,
  SlaveSessionData,
  UserAdminUpdate,
  UserData,
} from './types';

export { API_URL };

export function startGoogleLogin() {
  const returnTo = window.location.href;
  window.location.href = `${API_URL}/web/auth/google/start?return_to=${encodeURIComponent(returnTo)}`;
}

export async function logout() {
  await request<{ ok: true }>('post', '/web/auth/logout');
}

function query(params: Record<string, string | number | null | undefined>) {
  const items = Object.entries(params).filter((entry): entry is [string, string | number] => entry[1] !== null && entry[1] !== undefined && entry[1] !== '');
  if (items.length === 0) {
    return '';
  }
  return `?${items.map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`).join('&')}`;
}

export const api = {
  dashboard: {
    summary: () => request<DashboardSummary>('get', '/web/dashboard/summary'),
  },
  users: {
    fetchMe: async () => {
      try {
        return await request<UserData>('get', '/web/users/me');
      } catch {
        return null;
      }
    },
    list: (limit = 100, offset = 0) => request<UserData[]>('get', `/web/users${query({ limit, offset })}`),
    get: (userId: string) => request<UserData>('get', `/web/users/${encodeURIComponent(userId)}`),
    update: (userId: string, payload: UserAdminUpdate) => request<UserData>('patch', `/web/users/${encodeURIComponent(userId)}`, payload),
    delete: (userId: string) => request<{ ok: true }>('delete', `/web/users/${encodeURIComponent(userId)}`),
  },
  accessTokens: {
    listMine: () => request<AccessKeyData[]>('get', '/web/users/me/access-tokens'),
    createMine: (payload: AccessKeyCreate) => request<AccessKeyCreateResult>('post', '/web/users/me/access-tokens', payload),
    revokeMine: (accessKeyId: string) => request<{ ok: true }>('delete', `/web/users/me/access-tokens/${encodeURIComponent(accessKeyId)}`),
    listForUser: (userId: string) => request<AccessKeyData[]>('get', `/web/users/${encodeURIComponent(userId)}/access-tokens`),
    createForUser: (userId: string, payload: AccessKeyCreate) =>
      request<AccessKeyCreateResult>('post', `/web/users/${encodeURIComponent(userId)}/access-tokens`, payload),
    revokeForUser: (userId: string, accessKeyId: string) =>
      request<{ ok: true }>('delete', `/web/users/${encodeURIComponent(userId)}/access-tokens/${encodeURIComponent(accessKeyId)}`),
  },
  launchers: {
    list: (userId?: string) => request<LauncherSessionView[]>('get', `/web/launchers${query({ user_id: userId })}`),
    get: (launcherId: string) => request<LauncherSessionView>('get', `/web/launchers/${encodeURIComponent(launcherId)}`),
  },
  slaveSessions: {
    list: (userId?: string) => request<SlaveSessionData[]>('get', `/web/slave-sessions${query({ user_id: userId })}`),
    get: (sessionId: string) => request<SlaveSessionData>('get', `/web/slave-sessions/${encodeURIComponent(sessionId)}`),
    close: (sessionId: string) => request<{ ok: true }>('post', `/web/slave-sessions/${encodeURIComponent(sessionId)}/close`),
  },
};
