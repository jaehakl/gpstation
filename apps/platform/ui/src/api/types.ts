// YOU MUST OPEN ALL FRONTEND SOURCE FILES with UTF-8 ENCODING to READ KOREAN CHARACTERS CORRECTLY.

export type UserRole = 'admin' | 'user' | 'unauthorized';
export type UserDecimal = string | number;
export type JobTaskType = 'llm_single' | 'sdxl_t2i' | 'embedding';

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

export type JobData = {
  id: string;
  requester_user_id: string;
  worker_user_id?: string | null;
  worker_session_id?: string | null;
  task_type: string;
  status: string;
  priority: number;
  required_model_id?: string | null;
  required_vram_gb?: UserDecimal | null;
  required_trust_tier?: string | null;
  verification_policy?: string | null;
  price_limit_credit?: UserDecimal | null;
  estimated_cost_credit?: UserDecimal | null;
  final_cost_credit?: UserDecimal | null;
  worker_reward_credit?: UserDecimal | null;
  platform_fee_credit?: UserDecimal | null;
  lease_expires_at?: string | null;
  retry_count: number;
  max_retries: number;
  started_at?: string | null;
  completed_at?: string | null;
  failed_at?: string | null;
  cancelled_at?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  metadata_json?: Record<string, unknown>;
};

export type JobMessageData = {
  id: string;
  job_id: string;
  kind: string;
  role: string;
  status: string;
  parent_message_id?: string | null;
  created_by_user_id?: string | null;
  created_at?: string | null;
  metadata_json?: Record<string, unknown>;
};

export type JobMessagePartData = {
  id: string;
  message_id: string;
  object_id?: string | null;
  name?: string | null;
  part_type: string;
  sort_order: number;
  required: boolean;
  created_at?: string | null;
  metadata_json?: Record<string, unknown>;
};

export type StoredObjectData = {
  id: string;
  object_type: string;
  storage_backend: string;
  uri?: string | null;
  mime_type?: string | null;
  size_bytes?: number | null;
  sha256?: string | null;
  created_by_user_id?: string | null;
  expires_at?: string | null;
  created_at?: string | null;
  metadata_json?: Record<string, unknown>;
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

export type JobDetailData = {
  job: JobData;
  messages: JobMessageData[];
  message_parts: JobMessagePartData[];
  stored_objects: StoredObjectData[];
  worker_session?: WorkerSessionData | null;
};

export type JobCreateRequest = {
  task_type: JobTaskType;
  request_json: Record<string, unknown>;
};

export type JobCreateResult = {
  job_id: string;
  message_id: string;
  task_type: string;
  status: string;
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
