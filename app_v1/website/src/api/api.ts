import { API_URL, request } from './http';
import type {
  AccessKeyCreate,
  AccessKeyCreateResult,
  CrudAccessKeyRow,
  CrudColumn,
  CrudDeleteResponse,
  CrudLauncherRow,
  CrudListRequest,
  CrudListResponse,
  CrudSlaveSessionRow,
  CrudUpsertResponse,
  CrudUserRow,
  DashboardSummary,
  JobData,
  LauncherRuntimeData,
  LauncherReconcileResponse,
  UserData,
} from './types';

export { API_URL };

type CrudListOptions = Partial<CrudListRequest>;

type DbTable<Row extends object> = {
  label: string;
  readOnly?: boolean;
  columns: Partial<Record<Extract<keyof Row, string>, CrudColumn>>;
  listRows: (listRequest?: CrudListOptions) => Promise<CrudListResponse<Row>>;
  getRow: (rowId: string) => Promise<Row>;
  upsertRow?: (items: Partial<Row>[]) => Promise<CrudUpsertResponse[]>;
  deleteRows?: (ids: string[]) => Promise<CrudDeleteResponse>;
};

function crudListRequest(overrides: CrudListOptions = {}): CrudListRequest {
  return {
    offset: 0,
    limit: 100,
    selected_ids: [],
    search_text: null,
    text_filter: {},
    filter: {},
    sort: null,
    ...overrides,
  };
}

export const dbTables = {
  auth: {
    fetchMe: async () => {
      try {
        return await request<UserData>('get', '/web/auth/me');
      } catch {
        return null;
      }
    },
    startGoogleLogin: () => {
      const returnTo = window.location.href;
      window.location.href = `${API_URL}/web/auth/google/start?return_to=${encodeURIComponent(returnTo)}`;
    },
    logout: async () => {
      await request<{ ok: true }>('post', '/web/auth/logout');
    },
  },
  users: {
    label: '사용자',
    columns: {
      id: { label: 'ID', type: 'text', readOnly: true },
      email: { label: '이메일', type: 'text' },
      username: { label: '사용자명', type: 'text' },
      display_name: { label: '표시 이름', type: 'text' },
      role: { label: '역할', type: 'text', required: true },
      status: { label: '상태', type: 'text', required: true },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      updated_at: { label: '수정일', type: 'datetime', readOnly: true },
    },
    listRows: (listRequest?: CrudListOptions) =>
      request<CrudListResponse<CrudUserRow>>('post', '/web/crud/users/list', crudListRequest(listRequest)),
    getRow: (rowId: string) => request<CrudUserRow>('get', `/web/crud/users/${encodeURIComponent(rowId)}`),
    upsertRow: (items: Partial<CrudUserRow>[]) => request<CrudUpsertResponse[]>('post', '/web/crud/users/upsert', { items }),
    deleteRows: (ids: string[]) => request<CrudDeleteResponse>('post', '/web/crud/users/delete', { ids }),
  } satisfies DbTable<CrudUserRow>,
  accessKeys: {
    label: 'Access Token',
    readOnly: true,
    columns: {
      id: { label: 'ID', type: 'text', readOnly: true },
      user_id: { label: '사용자 ID', type: 'text', readOnly: true },
      key_type: { label: '키 유형', type: 'text', readOnly: true },
      name: { label: '이름', type: 'text', readOnly: true },
      key_prefix: { label: '키 접두사', type: 'text', readOnly: true },
      scopes: { label: '스코프', type: 'json', readOnly: true },
      status: { label: '상태', type: 'text', readOnly: true },
      rate_limit_per_minute: { label: '분당 제한', type: 'number', readOnly: true },
      allowed_ips: { label: '허용 IP', type: 'json', readOnly: true },
      allowed_origins: { label: '허용 Origin', type: 'json', readOnly: true },
      last_used_at: { label: '마지막 사용', type: 'datetime', readOnly: true },
      expires_at: { label: '만료일', type: 'datetime', readOnly: true },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      revoked_at: { label: '폐기일', type: 'datetime', readOnly: true },
    },
    listRows: (listRequest?: CrudListOptions) =>
      request<CrudListResponse<CrudAccessKeyRow>>('post', '/web/crud/access_keys/list', crudListRequest(listRequest)),
    getRow: (rowId: string) => request<CrudAccessKeyRow>('get', `/web/crud/access_keys/${encodeURIComponent(rowId)}`),
    deleteRows: (ids: string[]) => request<CrudDeleteResponse>('post', '/web/crud/access_keys/delete', { ids }),
    createMine: (payload: AccessKeyCreate) => request<AccessKeyCreateResult>('post', '/web/users/me/access-tokens', payload),
    createForUser: (userId: string, payload: AccessKeyCreate) =>
      request<AccessKeyCreateResult>('post', `/web/users/${encodeURIComponent(userId)}/access-tokens`, payload),
  } satisfies DbTable<CrudAccessKeyRow> & {
    createMine: (payload: AccessKeyCreate) => Promise<AccessKeyCreateResult>;
    createForUser: (userId: string, payload: AccessKeyCreate) => Promise<AccessKeyCreateResult>;
  },
  launchers: {
    label: 'Launcher',
    readOnly: true,
    columns: {
      id: { label: 'ID', type: 'text', readOnly: true },
      user_id: { label: '사용자 ID', type: 'text', readOnly: true },
      launcher_name: { label: 'Launcher 이름', type: 'text', readOnly: true },
      ip_address: { label: 'IP', type: 'text', readOnly: true },
      status: { label: '상태', type: 'text', readOnly: true },
      slave_app_ids: { label: 'Slave App', type: 'json', readOnly: true },
      active_session_ids: { label: '활성 세션', type: 'json', readOnly: true },
      connected_at: { label: '연결일', type: 'datetime', readOnly: true },
      last_heartbeat_at: { label: '마지막 하트비트', type: 'datetime', readOnly: true },
      disconnected_at: { label: '연결 종료일', type: 'datetime', readOnly: true },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      updated_at: { label: '수정일', type: 'datetime', readOnly: true },
    },
    listRows: (listRequest?: CrudListOptions) =>
      request<CrudListResponse<CrudLauncherRow>>('post', '/web/crud/launchers/list', crudListRequest(listRequest)),
    getRow: (rowId: string) => request<CrudLauncherRow>('get', `/web/crud/launchers/${encodeURIComponent(rowId)}`),
    reconcileDisconnected: () => request<LauncherReconcileResponse>('post', '/web/launchers/reconcile-disconnected'),
    runtime: () => request<LauncherRuntimeData[]>('get', '/web/launchers/runtime'),
    cancelCurrentJob: (launcherId: string) =>
      request<{ ok: true }>('post', `/web/launchers/${encodeURIComponent(launcherId)}/cancel-current-job`),
    resetWorker: (launcherId: string) =>
      request<{ ok: true }>('post', `/web/launchers/${encodeURIComponent(launcherId)}/reset-worker`),
  } satisfies DbTable<CrudLauncherRow> & {
    reconcileDisconnected: () => Promise<LauncherReconcileResponse>;
    runtime: () => Promise<LauncherRuntimeData[]>;
    cancelCurrentJob: (launcherId: string) => Promise<{ ok: true }>;
    resetWorker: (launcherId: string) => Promise<{ ok: true }>;
  },
  slaveSessions: {
    label: 'Slave Session',
    readOnly: true,
    columns: {
      id: { label: 'ID', type: 'text', readOnly: true },
      user_id: { label: '사용자 ID', type: 'text', readOnly: true },
      launcher_id: { label: 'Launcher ID', type: 'text', readOnly: true },
      slave_app_id: { label: 'Slave App', type: 'text', readOnly: true },
      master_ip_address: { label: 'Master IP', type: 'text', readOnly: true },
      master_user_agent: { label: 'Master User Agent', type: 'text', readOnly: true },
      status: { label: '상태', type: 'text', readOnly: true },
      ttl_seconds: { label: 'TTL', type: 'number', readOnly: true },
      expires_at: { label: '만료일', type: 'datetime', readOnly: true },
      ready_at: { label: '준비일', type: 'datetime', readOnly: true },
      closed_at: { label: '종료일', type: 'datetime', readOnly: true },
      last_error: { label: '마지막 오류', type: 'text', readOnly: true },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      updated_at: { label: '수정일', type: 'datetime', readOnly: true },
    },
    listRows: (listRequest?: CrudListOptions) =>
      request<CrudListResponse<CrudSlaveSessionRow>>('post', '/web/crud/slave_sessions/list', crudListRequest(listRequest)),
    getRow: (rowId: string) => request<CrudSlaveSessionRow>('get', `/web/crud/slave_sessions/${encodeURIComponent(rowId)}`),
    deleteRows: (ids: string[]) => request<CrudDeleteResponse>('post', '/web/crud/slave_sessions/delete', { ids }),
    close: (sessionId: string) => request<{ ok: true }>('post', `/web/slave-sessions/${encodeURIComponent(sessionId)}/close`),
  } satisfies DbTable<CrudSlaveSessionRow> & {
    close: (sessionId: string) => Promise<{ ok: true }>;
  },
  jobs: {
    list: (options?: { activeOnly?: boolean; limit?: number }) => {
      const params = new URLSearchParams();
      if (options?.activeOnly !== undefined) {
        params.set('active_only', String(options.activeOnly));
      }
      if (options?.limit !== undefined) {
        params.set('limit', String(options.limit));
      }
      const query = params.toString();
      return request<JobData[]>('get', `/web/jobs${query ? `?${query}` : ''}`);
    },
    kill: (jobId: string) => request<{ ok: true }>('post', `/web/jobs/${encodeURIComponent(jobId)}/kill`),
  },
  dashboard: {
    summary: async (): Promise<DashboardSummary> => {
      const [users, accessKeys, launchers, activeSessions] = await Promise.all([
        dbTables.users.listRows({ limit: 1 }),
        dbTables.accessKeys.listRows({ limit: 1 }),
        dbTables.launchers.listRows({ limit: 1 }),
        dbTables.slaveSessions.listRows({ limit: 1, text_filter: { status: ['starting', 'ready'] } }),
      ]);

      return {
        users: users.total,
        access_keys: accessKeys.total,
        launchers: launchers.total,
        active_sessions: activeSessions.total,
      };
    },
  },
};

export type DbTableName = keyof typeof dbTables;
