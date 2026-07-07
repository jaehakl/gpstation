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

export type UserAdminUpdate = {
  email?: string | null;
  username?: string | null;
  display_name?: string | null;
  role?: UserRole | null;
  status?: string | null;
};

export type AccessKeyData = {
  id: string;
  user_id: string;
  key_type: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  status: string;
  last_used_at?: string | null;
  expires_at?: string | null;
  created_at?: string | null;
  revoked_at?: string | null;
};

export type AccessKeyCreate = {
  name: string;
  scopes: AccessKeyScope[];
  expires_at?: string | null;
};

export type AccessKeyCreateResult = {
  access_key: AccessKeyData;
  secret: string;
};

export type LauncherSessionView = {
  id: string;
  user_id: string;
  launcher_name: string;
  status: string;
  slave_app_ids: string[];
  active_session_count: number;
  connected_at: string;
  last_heartbeat_at: string;
  ip_address?: string | null;
  disconnected_at?: string | null;
};

export type SlaveSessionData = {
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

export type DashboardSummary = {
  launchers: number;
  active_sessions: number;
  users: number;
  access_keys: number;
};
