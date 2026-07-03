// YOU MUST OPEN ALL FRONTEND SOURCE FILES with UTF-8 ENCODING to READ KOREAN CHARACTERS CORRECTLY.

export type UserRole = 'admin' | 'user' | 'unauthorized';
export type UserDecimal = string | number;

export type UserData = {
  id: string;
  email?: string | null;
  username?: string | null;
  display_name?: string | null;
  password_hash?: string | null;
  role?: UserRole | null;
  status?: string | null;
  is_active?: boolean | null;
  credit_balance?: UserDecimal | null;
  credit_pending?: UserDecimal | null;
  credit_withdrawable?: UserDecimal | null;
  trust_score?: UserDecimal | null;
  trust_tier?: string | null;
  success_job_count?: number | null;
  failed_job_count?: number | null;
  disputed_job_count?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
  last_login_at?: string | null;
  metadata_json?: Record<string, unknown>;
  roles: string[];
};

export type UserAdminUpdate = {
  email?: string | null;
  username?: string | null;
  display_name?: string | null;
  password_hash?: string | null;
  role?: UserRole | null;
  status?: string | null;
  credit_balance?: UserDecimal | null;
  credit_pending?: UserDecimal | null;
  credit_withdrawable?: UserDecimal | null;
  trust_score?: UserDecimal | null;
  trust_tier?: string | null;
  success_job_count?: number | null;
  failed_job_count?: number | null;
  disputed_job_count?: number | null;
  last_login_at?: string | null;
  metadata_json?: Record<string, unknown> | null;
};

export type AccessKeyData = {
  id: string;
  user_id: string;
  key_type: string;
  name: string;
  key_prefix: string;
  status: string;
  last_used_at?: string | null;
  expires_at?: string | null;
  created_at?: string | null;
  revoked_at?: string | null;
};

export type AccessKeyCreate = {
  name: string;
  expires_at?: string | null;
};

export type AccessKeyCreateResult = {
  access_key: AccessKeyData;
  secret: string;
};

export type WorkerSessionData = {
  id: string;
  user_id: string;
  status: string;
  accepting_jobs: boolean;
  ip_address?: string | null;
  user_agent?: string | null;
  client_version?: string | null;
  gpu_name?: string | null;
  gpu_vendor?: string | null;
  vram_total_mb?: number | null;
  vram_available_mb?: number | null;
  gpu_utilization_pct?: UserDecimal | null;
  gpu_temperature_c?: UserDecimal | null;
  supported_task_types?: string[] | null;
  installed_model_ids?: string[] | null;
  current_job_id?: string | null;
  connected_at?: string | null;
  last_heartbeat_at?: string | null;
  disconnected_at?: string | null;
  expires_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  metadata_json?: Record<string, unknown>;
};

export type DbColumnType =
  | 'id'
  | 'text'
  | 'datetime'
  | 'boolean'
  | 'number'
  | 'decimal'
  | 'json'
  | 'binary'
  | 'list'
  | 'fk';

export type DbColumn = {
  label: string;
  type: DbColumnType;
  readOnly?: boolean;
  required?: boolean;
  targetTable?: string;
};

export type DbTableColumns = Record<string, DbColumn>;
