import { headers } from 'next/headers';
import type {
  ExampleRecord,
  GetListRequest,
  GetListResponse,
} from './types';

const randomExampleRequest: GetListRequest = {
  offset: 0,
  limit: 1,
  selected_ids: [],
  search_text: null,
  text_filter: {},
  filter: {},
  sort: null,
  random: true,
};

function getServerApiBaseUrl() {
  const explicitUrl = process.env.API_INTERNAL_BASE_URL?.trim();
  if (explicitUrl) {
    return explicitUrl.replace(/\/+$/, '');
  }

  const publicUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (publicUrl?.startsWith('http://') || publicUrl?.startsWith('https://')) {
    return publicUrl.replace(/\/+$/, '');
  }

  return 'http://127.0.0.1:8000';
}

async function readErrorMessage(response: Response) {
  const fallback = `${response.status} ${response.statusText}`.trim();
  const text = await response.text();

  if (!text) {
    return fallback;
  }

  try {
    const data = JSON.parse(text) as {
      detail?: unknown;
      error?: unknown;
      message?: unknown;
    };
    const value = data.detail ?? data.error ?? data.message;

    if (typeof value === 'string') {
      return value;
    }

    return value === undefined ? text : JSON.stringify(value);
  } catch {
    return text;
  }
}

async function requestServerJson<T>(path: string, body: unknown): Promise<T> {
  const inboundHeaders = await headers();
  const cookie = inboundHeaders.get('cookie');
  const response = await fetch(`${getServerApiBaseUrl()}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(cookie ? { cookie } : {}),
    },
    body: JSON.stringify(body),
    cache: 'no-store',
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  return (await response.json()) as T;
}

export async function fetchRandomExampleId() {
  const response = await requestServerJson<GetListResponse<ExampleRecord>>(
    '/example/list',
    randomExampleRequest,
  );
  return response.items[0]?.id ?? null;
}
