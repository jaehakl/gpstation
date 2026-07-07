import axios from 'axios';

const apiBaseUrl = process.env.NEXT_PUBLIC_GPSTATION_V1_API_URL || 'http://127.0.0.1:8100';
export const API_URL = apiBaseUrl.replace(/\/+$/, '') || 'http://127.0.0.1:8100';

type HttpMethod = 'get' | 'post' | 'patch' | 'delete';

const apiClient = axios.create({
  baseURL: API_URL,
  withCredentials: true,
});

let refreshPromise: Promise<void> | null = null;

function getResponseStatus(error: unknown): number | undefined {
  if (typeof error !== 'object' || error === null || !('response' in error)) {
    return undefined;
  }
  const response = (error as { response?: { status?: unknown } }).response;
  return typeof response?.status === 'number' ? response.status : undefined;
}

async function send<T>(method: HttpMethod, url: string, data?: unknown): Promise<T> {
  const response = await apiClient.request<T>({
    method,
    url,
    ...(data === undefined ? {} : { data }),
  });
  return response.data;
}

async function refreshAuth() {
  if (!refreshPromise) {
    refreshPromise = send<{ ok: true }>('get', '/web/auth/refresh')
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
