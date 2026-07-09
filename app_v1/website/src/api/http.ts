import axios from 'axios';

const apiBaseUrl = import.meta.env.VITE_GPSTATION_V1_API_URL || '';
export const API_URL = apiBaseUrl.replace(/\/+$/, '');

type HttpMethod = 'get' | 'post' | 'patch' | 'delete';
type CsrfResponse = { csrf_token: string };

const apiClient = axios.create({
  baseURL: API_URL,
  withCredentials: true,
});

let refreshPromise: Promise<void> | null = null;
let csrfToken: string | null = null;
let csrfPromise: Promise<string> | null = null;

function getResponseStatus(error: unknown): number | undefined {
  if (typeof error !== 'object' || error === null || !('response' in error)) {
    return undefined;
  }
  const response = (error as { response?: { status?: unknown } }).response;
  return typeof response?.status === 'number' ? response.status : undefined;
}

function usesCsrf(method: HttpMethod, url: string): boolean {
  return method !== 'get' && url.startsWith('/web/');
}

async function fetchCsrfToken(): Promise<string> {
  if (!csrfPromise) {
    csrfPromise = apiClient
      .get<CsrfResponse>('/web/auth/csrf')
      .then((response) => response.data.csrf_token)
      .then((token) => {
        csrfToken = token;
        return token;
      })
      .finally(() => {
        csrfPromise = null;
      });
  }
  return csrfPromise;
}

async function ensureCsrfToken(): Promise<string> {
  if (csrfToken) {
    return csrfToken;
  }
  return fetchCsrfToken();
}

async function send<T>(method: HttpMethod, url: string, data?: unknown, retryCsrf = true): Promise<T> {
  const csrfProtected = usesCsrf(method, url);
  const headers = csrfProtected ? { 'X-CSRF-Token': await ensureCsrfToken() } : undefined;
  try {
    const response = await apiClient.request<T>({
      method,
      url,
      headers,
      ...(data === undefined ? {} : { data }),
    });
    return response.data;
  } catch (error) {
    if (csrfProtected && retryCsrf && getResponseStatus(error) === 403) {
      csrfToken = null;
      return send<T>(method, url, data, false);
    }
    throw error;
  }
}

async function refreshAuth() {
  if (!refreshPromise) {
    refreshPromise = send<{ ok: true }>('post', '/web/auth/refresh')
      .then(() => undefined)
      .finally(() => {
        refreshPromise = null;
      });
  }
  await refreshPromise;
}

export async function request<T>(method: HttpMethod, url: string, data?: unknown): Promise<T> {
  try {
    return await send<T>(method, url, data);
  } catch (error) {
    if (url === '/web/auth/refresh' || getResponseStatus(error) !== 401) {
      throw error;
    }
    await refreshAuth();
    return send<T>(method, url, data);
  }
}
