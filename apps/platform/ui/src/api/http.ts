// YOU MUST OPEN ALL FRONTEND SOURCE FILES with UTF-8 ENCODING to READ KOREAN CHARACTERS CORRECTLY.

import axios from 'axios';

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '/api';
export const API_URL = apiBaseUrl.replace(/\/+$/, '') || '/api';

type HttpMethod = 'get' | 'post' | 'delete';

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
    refreshPromise = send<{ ok: true }>('get', '/auth/refresh')
      .then(() => undefined)
      .finally(() => {
        refreshPromise = null;
      });
  }

  await refreshPromise;
}

export async function request<T>(
  method: HttpMethod,
  url: string,
  data?: unknown,
): Promise<T> {
  try {
    return await send<T>(method, url, data);
  } catch (error) {
    if (url === '/auth/refresh' || getResponseStatus(error) !== 401) {
      throw error;
    }

    await refreshAuth();
    return send<T>(method, url, data);
  }
}
