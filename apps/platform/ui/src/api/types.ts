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
