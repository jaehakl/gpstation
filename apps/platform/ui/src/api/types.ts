// YOU MUST OPEN ALL FRONTEND SOURCE FILES with UTF-8 ENCODING to READ KOREAN CHARACTERS CORRECTLY.

export type UserData = {
  id: string;
  email?: string | null;
  username?: string | null;
  display_name?: string | null;
  role?: string | null;
  status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  last_login_at?: string | null;
  roles: string[];
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
