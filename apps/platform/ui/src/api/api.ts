// YOU MUST OPEN ALL FRONTEND SOURCE FILES with UTF-8 ENCODING to READ KOREAN CHARACTERS CORRECTLY.

import { API_URL, request } from './http';
import type {
  AccessKeyCreate,
  AccessKeyCreateResult,
  AccessKeyData,
  DbTableColumns,
  UserAdminUpdate,
  UserData,
  WorkerSessionData,
} from './types';

export { API_URL };

type DbTableDefinition = {
  label: string;
  columns: DbTableColumns;
};

export function startGoogleLogin() {
  const returnTo = window.location.href;
  window.location.href = `${API_URL}/web/auth/google/start?return_to=${encodeURIComponent(returnTo)}`;
}

export async function logout() {
  await request<{ ok: true }>('post', '/web/auth/logout');
}

export const dbTables = {
  User: {
    label: '사용자',
    columns: {
      id: { label: 'ID', type: 'id', readOnly: true },
      email: { label: '이메일', type: 'text' },
      username: { label: '사용자명', type: 'text' },
      display_name: { label: '표시 이름', type: 'text' },
      password_hash: { label: '비밀번호 해시', type: 'text' },
      role: { label: '권한', type: 'text' },
      status: { label: '상태', type: 'text' },
      credit_balance: { label: '크레딧 잔액', type: 'decimal' },
      credit_pending: { label: '대기 크레딧', type: 'decimal' },
      credit_withdrawable: { label: '출금 가능 크레딧', type: 'decimal' },
      trust_score: { label: '신뢰 점수', type: 'decimal' },
      trust_tier: { label: '신뢰 등급', type: 'text' },
      success_job_count: { label: '성공 작업 수', type: 'number' },
      failed_job_count: { label: '실패 작업 수', type: 'number' },
      disputed_job_count: { label: '분쟁 작업 수', type: 'number' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      updated_at: { label: '수정일', type: 'datetime', readOnly: true },
      last_login_at: { label: '마지막 로그인', type: 'datetime', readOnly: true },
      metadata_json: { label: '메타데이터', type: 'json' },
    },
    fetchMe: async () => {
      try {
        return await request<UserData>('get', '/web/users/me');
      } catch {
        return null;
      }
    },
    listUsers: (limit: number, offset: number) =>
      request<UserData[]>(
        'get',
        `/web/users?limit=${encodeURIComponent(String(limit))}&offset=${encodeURIComponent(String(offset))}`,
      ),
    getUser: (userId: string) =>
      request<UserData>('get', `/web/users/${encodeURIComponent(userId)}`),
    updateUser: (userId: string, payload: UserAdminUpdate) =>
      request<UserData>('patch', `/web/users/${encodeURIComponent(userId)}`, payload),
    deleteUser: (userId: string) =>
      request<{ ok: true }>('delete', `/web/users/${encodeURIComponent(userId)}`),
  },

  WorkerSession: {
    label: '워커 세션',
    columns: {
      id: { label: 'ID', type: 'id', readOnly: true },
      user_id: { label: '사용자', type: 'fk', targetTable: 'User', required: true },
      status: { label: '상태', type: 'text', required: true },
      accepting_jobs: { label: '작업 수락', type: 'boolean' },
      session_token_hash: { label: '세션 토큰 해시', type: 'binary' },
      ip_address: { label: 'IP 주소', type: 'text' },
      user_agent: { label: 'User Agent', type: 'text' },
      client_version: { label: '클라이언트 버전', type: 'text' },
      gpu_name: { label: 'GPU 이름', type: 'text' },
      gpu_vendor: { label: 'GPU 벤더', type: 'text' },
      vram_total_mb: { label: '총 VRAM MB', type: 'number' },
      vram_available_mb: { label: '가용 VRAM MB', type: 'number' },
      gpu_utilization_pct: { label: 'GPU 사용률', type: 'decimal' },
      gpu_temperature_c: { label: 'GPU 온도', type: 'decimal' },
      supported_task_types: { label: '지원 작업 유형', type: 'list' },
      installed_model_ids: { label: '설치 모델', type: 'list' },
      current_job_id: { label: '현재 작업', type: 'fk', targetTable: 'Job' },
      connected_at: { label: '연결일', type: 'datetime' },
      last_heartbeat_at: { label: '마지막 하트비트', type: 'datetime' },
      disconnected_at: { label: '연결 종료일', type: 'datetime' },
      expires_at: { label: '만료일', type: 'datetime' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      updated_at: { label: '수정일', type: 'datetime', readOnly: true },
      metadata_json: { label: '메타데이터', type: 'json' },
    },
    listWorkerSessions: () =>
      request<WorkerSessionData[]>('get', '/web/worker-sessions'),
  },

  AccessKey: {
    label: '접근 키',
    columns: {
      id: { label: 'ID', type: 'id', readOnly: true },
      user_id: { label: '사용자', type: 'fk', targetTable: 'User', required: true },
      key_type: { label: '키 유형', type: 'text', required: true },
      name: { label: '이름', type: 'text', required: true },
      key_prefix: { label: '키 접두사', type: 'text', readOnly: true },
      key_hash: { label: '키 해시', type: 'binary', readOnly: true },
      scopes: { label: '스코프', type: 'list' },
      status: { label: '상태', type: 'text' },
      rate_limit_per_minute: { label: '분당 제한', type: 'number' },
      allowed_ips: { label: '허용 IP', type: 'list' },
      allowed_origins: { label: '허용 Origin', type: 'list' },
      last_used_at: { label: '마지막 사용일', type: 'datetime', readOnly: true },
      expires_at: { label: '만료일', type: 'datetime' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      revoked_at: { label: '폐기일', type: 'datetime' },
      metadata_json: { label: '메타데이터', type: 'json' },
    },
    listMyAccessKeys: () =>
      request<AccessKeyData[]>('get', '/web/users/me/access-keys'),
    createMyAccessKey: (payload: AccessKeyCreate) =>
      request<AccessKeyCreateResult>('post', '/web/users/me/access-keys', payload),
    revokeMyAccessKey: (accessKeyId: string) =>
      request<{ ok: true }>('delete', `/web/users/me/access-keys/${encodeURIComponent(accessKeyId)}`),
  },

  Job: {
    label: '작업',
    columns: {
      id: { label: 'ID', type: 'id', readOnly: true },
      requester_user_id: { label: '요청자', type: 'fk', targetTable: 'User', required: true },
      worker_user_id: { label: '워커 사용자', type: 'fk', targetTable: 'User' },
      worker_session_id: { label: '워커 세션', type: 'fk', targetTable: 'WorkerSession' },
      task_type: { label: '작업 유형', type: 'text', required: true },
      status: { label: '상태', type: 'text', required: true },
      priority: { label: '우선순위', type: 'number' },
      required_model_id: { label: '필요 모델', type: 'text' },
      required_vram_gb: { label: '필요 VRAM GB', type: 'decimal' },
      required_trust_tier: { label: '필요 신뢰 등급', type: 'text' },
      verification_policy: { label: '검증 정책', type: 'text' },
      price_limit_credit: { label: '가격 한도', type: 'decimal' },
      estimated_cost_credit: { label: '예상 비용', type: 'decimal' },
      final_cost_credit: { label: '최종 비용', type: 'decimal' },
      worker_reward_credit: { label: '워커 보상', type: 'decimal' },
      platform_fee_credit: { label: '플랫폼 수수료', type: 'decimal' },
      lease_expires_at: { label: '임대 만료일', type: 'datetime' },
      retry_count: { label: '재시도 수', type: 'number' },
      max_retries: { label: '최대 재시도', type: 'number' },
      started_at: { label: '시작일', type: 'datetime' },
      completed_at: { label: '완료일', type: 'datetime' },
      failed_at: { label: '실패일', type: 'datetime' },
      cancelled_at: { label: '취소일', type: 'datetime' },
      error_code: { label: '오류 코드', type: 'text' },
      error_message: { label: '오류 메시지', type: 'text' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      updated_at: { label: '수정일', type: 'datetime', readOnly: true },
      metadata_json: { label: '메타데이터', type: 'json' },
    },
  },

  JobMessage: {
    label: '작업 메시지',
    columns: {
      id: { label: 'ID', type: 'id', readOnly: true },
      job_id: { label: '작업', type: 'fk', targetTable: 'Job', required: true },
      kind: { label: '종류', type: 'text', required: true },
      role: { label: '역할', type: 'text', required: true },
      status: { label: '상태', type: 'text', required: true },
      parent_message_id: { label: '상위 메시지', type: 'fk', targetTable: 'JobMessage' },
      created_by_user_id: { label: '작성자', type: 'fk', targetTable: 'User' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      metadata_json: { label: '메타데이터', type: 'json' },
    },
  },

  StoredObject: {
    label: '저장 객체',
    columns: {
      id: { label: 'ID', type: 'id', readOnly: true },
      object_type: { label: '객체 유형', type: 'text', required: true },
      storage_backend: { label: '저장소', type: 'text', required: true },
      uri: { label: 'URI', type: 'text' },
      inline_content: { label: '인라인 콘텐츠', type: 'binary' },
      mime_type: { label: 'MIME 유형', type: 'text' },
      size_bytes: { label: '크기 bytes', type: 'number' },
      sha256: { label: 'SHA-256', type: 'text' },
      created_by_user_id: { label: '작성자', type: 'fk', targetTable: 'User' },
      expires_at: { label: '만료일', type: 'datetime' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      metadata_json: { label: '메타데이터', type: 'json' },
    },
  },

  JobMessagePart: {
    label: '작업 메시지 파트',
    columns: {
      id: { label: 'ID', type: 'id', readOnly: true },
      message_id: { label: '메시지', type: 'fk', targetTable: 'JobMessage', required: true },
      object_id: { label: '저장 객체', type: 'fk', targetTable: 'StoredObject' },
      name: { label: '이름', type: 'text' },
      part_type: { label: '파트 유형', type: 'text', required: true },
      sort_order: { label: '정렬 순서', type: 'number' },
      required: { label: '필수', type: 'boolean' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      metadata_json: { label: '메타데이터', type: 'json' },
    },
  },

  JobEvent: {
    label: '작업 이벤트',
    columns: {
      id: { label: 'ID', type: 'id', readOnly: true },
      job_id: { label: '작업', type: 'fk', targetTable: 'Job', required: true },
      event_type: { label: '이벤트 유형', type: 'text', required: true },
      actor_user_id: { label: '행위자', type: 'fk', targetTable: 'User' },
      actor_role: { label: '행위자 역할', type: 'text' },
      from_status: { label: '이전 상태', type: 'text' },
      to_status: { label: '다음 상태', type: 'text' },
      message_id: { label: '메시지', type: 'fk', targetTable: 'JobMessage' },
      object_id: { label: '저장 객체', type: 'fk', targetTable: 'StoredObject' },
      error_code: { label: '오류 코드', type: 'text' },
      error_message: { label: '오류 메시지', type: 'text' },
      request_id: { label: '요청 ID', type: 'text' },
      trace_id: { label: 'Trace ID', type: 'text' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      metadata_json: { label: '메타데이터', type: 'json' },
    },
  },

  CreditLedger: {
    label: '크레딧 원장',
    columns: {
      id: { label: 'ID', type: 'id', readOnly: true },
      user_id: { label: '사용자', type: 'fk', targetTable: 'User', required: true },
      job_id: { label: '작업', type: 'fk', targetTable: 'Job' },
      counterparty_user_id: { label: '상대 사용자', type: 'fk', targetTable: 'User' },
      type: { label: '유형', type: 'text', required: true },
      amount: { label: '금액', type: 'decimal', required: true },
      balance_type: { label: '잔액 유형', type: 'text', required: true },
      status: { label: '상태', type: 'text', required: true },
      related_ledger_id: { label: '관련 원장', type: 'fk', targetTable: 'CreditLedger' },
      idempotency_key: { label: '멱등 키', type: 'text' },
      reason: { label: '사유', type: 'text' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      settled_at: { label: '정산일', type: 'datetime' },
      metadata_json: { label: '메타데이터', type: 'json' },
    },
  },
} satisfies Record<string, DbTableDefinition & Record<string, unknown>>;

export type DbTableName = keyof typeof dbTables;
