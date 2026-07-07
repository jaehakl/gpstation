export type UserRole = 'admin' | 'user' | 'unauthorized';
export type AccessKeyScope = 'client' | 'launcher';

export type UserData = {
  id: string;
  email?: string | null;
  username?: string | null;
  display_name?: string | null;
  role: UserRole;
  status: string;
  is_active: boolean;
  roles: string[];
  created_at?: string | null;
  updated_at?: string | null;
};

export type AccessKeyCreate = {
  name: string;
  scopes: AccessKeyScope[];
  expires_at?: string | null;
};

export type AccessKeyCreateResult = {
  access_key: CrudAccessKeyRow;
  secret: string;
};

export type DashboardSummary = {
  launchers: number;
  active_sessions: number;
  users: number;
  access_keys: number;
};

export type CrudSort = [string, 'asc' | 'desc'] | null;

export type CrudListRequest = {
  offset: number;
  limit: number | null;
  selected_ids: string[];
  search_text: string | null;
  text_filter: Record<string, string[]>;
  filter: Record<string, unknown[]>;
  sort: CrudSort;
};

export type CrudListResponse<T> = {
  total: number;
  items: T[];
};

export type CrudUpsertResponse = {
  id: string;
};

export type CrudDeleteResponse = {
  deleted: number;
};

export type LauncherReconcileResponse = {
  ok: true;
  launchers: number;
  slave_sessions: number;
};

export type CrudColumnType = 'text' | 'number' | 'datetime' | 'json';

export type CrudColumn = {
  label: string;
  type: CrudColumnType;
  readOnly?: boolean;
  required?: boolean;
};

export type CrudUserRow = {
  id: string;
  email?: string | null;
  username?: string | null;
  display_name?: string | null;
  role: UserRole;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
  access_key_ids?: string[];
  launcher_ids?: string[];
  slave_session_ids?: string[];
};

export type CrudAccessKeyRow = {
  id: string;
  user_id: string;
  key_type: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  status: string;
  rate_limit_per_minute?: number | null;
  allowed_ips?: string[] | null;
  allowed_origins?: string[] | null;
  last_used_at?: string | null;
  expires_at?: string | null;
  created_at?: string | null;
  revoked_at?: string | null;
};

export type CrudLauncherRow = {
  id: string;
  user_id: string;
  launcher_name: string;
  ip_address?: string | null;
  status: string;
  slave_app_ids: string[];
  active_session_ids: string[];
  connected_at: string;
  last_heartbeat_at: string;
  disconnected_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  slave_session_ids?: string[];
};

export type CrudSlaveSessionRow = {
  id: string;
  user_id: string;
  launcher_id?: string | null;
  slave_app_id: string;
  master_ip_address?: string | null;
  master_user_agent?: string | null;
  status: string;
  ttl_seconds: number;
  expires_at: string;
  ready_at?: string | null;
  closed_at?: string | null;
  last_error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};
