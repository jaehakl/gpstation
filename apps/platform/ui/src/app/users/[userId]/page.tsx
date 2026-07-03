'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { Clipboard, KeyRound, RefreshCw, Save, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { dbTables } from '../../../api/api';
import type { AccessKeyData, UserAdminUpdate, UserData, UserRole } from '../../../api/types';
import { useAuthStore } from '../../../stores/authStore';

type UserFormState = {
  email: string;
  username: string;
  display_name: string;
  password_hash: string;
  role: UserRole;
  status: string;
  credit_balance: string;
  credit_pending: string;
  credit_withdrawable: string;
  trust_score: string;
  trust_tier: string;
  success_job_count: string;
  failed_job_count: string;
  disputed_job_count: string;
  last_login_at: string;
  metadata_json: string;
};

const roleOptions: UserRole[] = ['admin', 'user', 'unauthorized'];

function formatDate(value: string | null | undefined) {
  if (!value) {
    return '-';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString('ko-KR');
}

function displayUserName(user: UserData) {
  return user.display_name?.trim() || user.username || user.email || user.id;
}

function userToForm(user: UserData): UserFormState {
  return {
    email: user.email ?? '',
    username: user.username ?? '',
    display_name: user.display_name ?? '',
    password_hash: user.password_hash ?? '',
    role: user.role ?? 'unauthorized',
    status: user.status ?? 'active',
    credit_balance: String(user.credit_balance ?? '0'),
    credit_pending: String(user.credit_pending ?? '0'),
    credit_withdrawable: String(user.credit_withdrawable ?? '0'),
    trust_score: String(user.trust_score ?? '0'),
    trust_tier: user.trust_tier ?? 'standard',
    success_job_count: String(user.success_job_count ?? 0),
    failed_job_count: String(user.failed_job_count ?? 0),
    disputed_job_count: String(user.disputed_job_count ?? 0),
    last_login_at: user.last_login_at ?? '',
    metadata_json: JSON.stringify(user.metadata_json ?? {}, null, 2),
  };
}

function nullableText(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function nullableAccessKeyExpiresAt(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  const date = new Date(trimmed);
  if (Number.isNaN(date.getTime())) {
    throw new Error('만료일 값이 올바르지 않습니다.');
  }
  return date.toISOString();
}

function requiredText(value: string, label: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    throw new Error(`${label} 값을 입력해야 합니다.`);
  }
  return trimmed;
}

function integerValue(value: string, label: string) {
  const trimmed = requiredText(value, label);
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed)) {
    throw new Error(`${label} 값은 정수여야 합니다.`);
  }
  return parsed;
}

function buildPayload(form: UserFormState): UserAdminUpdate {
  const parsedMetadata = JSON.parse(form.metadata_json || '{}') as unknown;
  if (typeof parsedMetadata !== 'object' || parsedMetadata === null || Array.isArray(parsedMetadata)) {
    throw new Error('메타데이터는 JSON object여야 합니다.');
  }

  return {
    email: nullableText(form.email),
    username: nullableText(form.username),
    display_name: nullableText(form.display_name),
    password_hash: nullableText(form.password_hash),
    role: form.role,
    status: requiredText(form.status, '상태'),
    credit_balance: requiredText(form.credit_balance, '크레딧 잔액'),
    credit_pending: requiredText(form.credit_pending, '대기 크레딧'),
    credit_withdrawable: requiredText(form.credit_withdrawable, '출금 가능 크레딧'),
    trust_score: requiredText(form.trust_score, '신뢰 점수'),
    trust_tier: requiredText(form.trust_tier, '신뢰 등급'),
    success_job_count: integerValue(form.success_job_count, '성공 작업 수'),
    failed_job_count: integerValue(form.failed_job_count, '실패 작업 수'),
    disputed_job_count: integerValue(form.disputed_job_count, '분쟁 작업 수'),
    last_login_at: nullableText(form.last_login_at),
    metadata_json: parsedMetadata as Record<string, unknown>,
  };
}

export default function UserDetailPage() {
  const params = useParams<{ userId?: string | string[] }>();
  const router = useRouter();
  const currentUser = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const refreshUser = useAuthStore((state) => state.refreshUser);
  const userIdParam = params.userId;
  const userId = Array.isArray(userIdParam) ? userIdParam[0] : userIdParam;
  const [loadedUser, setLoadedUser] = useState<UserData | null>(null);
  const [form, setForm] = useState<UserFormState | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [accessKeys, setAccessKeys] = useState<AccessKeyData[]>([]);
  const [accessKeyName, setAccessKeyName] = useState('');
  const [accessKeyExpiresAt, setAccessKeyExpiresAt] = useState('');
  const [createdAccessKeySecret, setCreatedAccessKeySecret] = useState<string | null>(null);
  const [isAccessKeyLoading, setIsAccessKeyLoading] = useState(false);
  const [isAccessKeyCreating, setIsAccessKeyCreating] = useState(false);
  const [revokingAccessKeyId, setRevokingAccessKeyId] = useState<string | null>(null);
  const [accessKeyError, setAccessKeyError] = useState<string | null>(null);
  const [accessKeyMessage, setAccessKeyMessage] = useState<string | null>(null);

  const isAdmin = currentUser?.roles.includes('admin') || currentUser?.role === 'admin';
  const isSelf = Boolean(currentUser && userId && currentUser.id === userId);
  const canManageAccessKeys = Boolean(
    isSelf &&
      currentUser &&
      (currentUser.roles.includes('admin') ||
        currentUser.roles.includes('user') ||
        currentUser.role === 'admin' ||
        currentUser.role === 'user'),
  );

  const loadUser = useCallback(async () => {
    if (!authReady || !currentUser || !userId) {
      return;
    }

    setIsLoading(true);
    setError(null);
    setMessage(null);
    try {
      const nextUser = await dbTables.User.getUser(userId);
      setLoadedUser(nextUser);
      setForm(userToForm(nextUser));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '사용자 정보를 불러오지 못했습니다.');
    } finally {
      setIsLoading(false);
    }
  }, [authReady, currentUser, userId]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadUser();
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [loadUser]);

  const loadAccessKeys = useCallback(async () => {
    if (!authReady || !currentUser || !isSelf || !canManageAccessKeys) {
      setAccessKeys([]);
      return;
    }

    setIsAccessKeyLoading(true);
    setAccessKeyError(null);
    try {
      setAccessKeys(await dbTables.AccessKey.listMyAccessKeys());
    } catch (loadError) {
      setAccessKeyError(loadError instanceof Error ? loadError.message : 'AccessKey 목록을 불러오지 못했습니다.');
    } finally {
      setIsAccessKeyLoading(false);
    }
  }, [authReady, canManageAccessKeys, currentUser, isSelf]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadAccessKeys();
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [loadAccessKeys]);

  async function saveUser() {
    if (!userId || !form) {
      return;
    }

    setIsSaving(true);
    setError(null);
    setMessage(null);
    try {
      const updatedUser = await dbTables.User.updateUser(userId, buildPayload(form));
      setLoadedUser(updatedUser);
      setForm(userToForm(updatedUser));
      setMessage('저장했습니다.');
      if (currentUser?.id === userId) {
        await refreshUser();
      }
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '사용자 정보를 저장하지 못했습니다.');
    } finally {
      setIsSaving(false);
    }
  }

  async function deleteUser() {
    if (!userId || !window.confirm('이 계정을 삭제할까요?')) {
      return;
    }

    setIsDeleting(true);
    setError(null);
    setMessage(null);
    try {
      await dbTables.User.deleteUser(userId);
      if (isSelf) {
        await refreshUser();
        router.push('/login');
        return;
      }
      router.push('/users');
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : '계정을 삭제하지 못했습니다.');
    } finally {
      setIsDeleting(false);
    }
  }

  async function createAccessKey() {
    setIsAccessKeyCreating(true);
    setAccessKeyError(null);
    setAccessKeyMessage(null);
    setCreatedAccessKeySecret(null);
    try {
      const result = await dbTables.AccessKey.createMyAccessKey({
        name: requiredText(accessKeyName, 'AccessKey 이름'),
        expires_at: nullableAccessKeyExpiresAt(accessKeyExpiresAt),
      });
      setAccessKeys((items) => [result.access_key, ...items.filter((item) => item.id !== result.access_key.id)]);
      setAccessKeyName('');
      setAccessKeyExpiresAt('');
      setCreatedAccessKeySecret(result.secret);
      setAccessKeyMessage('AccessKey를 생성했습니다. 원문 키는 지금만 확인할 수 있습니다.');
    } catch (createError) {
      setAccessKeyError(createError instanceof Error ? createError.message : 'AccessKey를 생성하지 못했습니다.');
    } finally {
      setIsAccessKeyCreating(false);
    }
  }

  async function revokeAccessKey(accessKeyId: string) {
    if (!window.confirm('이 AccessKey를 폐기할까요?')) {
      return;
    }

    setRevokingAccessKeyId(accessKeyId);
    setAccessKeyError(null);
    setAccessKeyMessage(null);
    try {
      await dbTables.AccessKey.revokeMyAccessKey(accessKeyId);
      setCreatedAccessKeySecret(null);
      setAccessKeyMessage('AccessKey를 폐기했습니다.');
      await loadAccessKeys();
    } catch (revokeError) {
      setAccessKeyError(revokeError instanceof Error ? revokeError.message : 'AccessKey를 폐기하지 못했습니다.');
    } finally {
      setRevokingAccessKeyId(null);
    }
  }

  async function copyCreatedAccessKeySecret() {
    if (!createdAccessKeySecret) {
      return;
    }

    setAccessKeyError(null);
    try {
      await navigator.clipboard.writeText(createdAccessKeySecret);
      setAccessKeyMessage('AccessKey를 복사했습니다.');
    } catch {
      setAccessKeyError('클립보드에 복사하지 못했습니다.');
    }
  }

  if (!authReady) {
    return (
      <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center px-4 text-sm font-bold text-[var(--app-muted)]">
        사용자 정보를 확인 중입니다.
      </div>
    );
  }

  if (!currentUser) {
    return (
      <div className="mx-auto flex min-h-[calc(100vh-3.5rem)] max-w-xl items-center px-4 py-10">
        <section className="w-full rounded-lg border border-[var(--app-border)] bg-white p-6 shadow-sm">
          <h1 className="text-2xl font-black">로그인이 필요합니다</h1>
          <Link
            href="/login"
            className="mt-5 inline-flex h-11 w-full items-center justify-center rounded-lg border border-[#b02c2c] bg-[var(--app-accent)] px-3 text-sm font-extrabold text-white transition hover:bg-[var(--app-accent-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
          >
            로그인으로 이동
          </Link>
        </section>
      </div>
    );
  }

  if (!isAdmin && !isSelf) {
    return (
      <div className="mx-auto flex min-h-[calc(100vh-3.5rem)] max-w-xl items-center px-4 py-10">
        <section className="w-full rounded-lg border border-[var(--app-border)] bg-white p-6 shadow-sm">
          <h1 className="text-2xl font-black">접근할 수 없습니다</h1>
          <p className="mt-3 text-sm font-semibold leading-6 text-[var(--app-muted)]">
            자신의 계정 정보만 확인할 수 있습니다.
          </p>
          <Link
            href={`/users/${currentUser.id}`}
            className="mt-5 inline-flex h-11 w-full items-center justify-center rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
          >
            내 계정으로 이동
          </Link>
        </section>
      </div>
    );
  }

  return (
    <div className="mx-auto grid w-full max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[minmax(0,1fr)_380px] lg:px-8">
      <section className="rounded-lg border border-[var(--app-border)] bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.14em] text-[var(--app-muted)]">
              User
            </p>
            <h1 className="mt-1 text-2xl font-black">
              {loadedUser ? displayUserName(loadedUser) : '사용자'}
            </h1>
          </div>
          {loadedUser ? (
            <span className="inline-flex h-8 w-fit items-center rounded-full border border-[var(--app-border)] bg-[#fafafa] px-3 text-xs font-black">
              {loadedUser.role ?? '-'} / {loadedUser.status ?? '-'}
            </span>
          ) : null}
        </div>

        {error ? (
          <p className="mt-4 rounded-lg border border-[#f2c4c4] bg-[var(--app-accent-soft)] px-3 py-2 text-sm font-bold text-[#9a2525]">
            {error}
          </p>
        ) : null}

        {message ? (
          <p className="mt-4 rounded-lg border border-[#b9dfc1] bg-[#f1fff3] px-3 py-2 text-sm font-bold text-[#1f6f2e]">
            {message}
          </p>
        ) : null}

        {isLoading ? (
          <p className="mt-5 rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa] px-4 py-8 text-center text-sm font-bold text-[var(--app-muted)]">
            사용자 정보를 불러오는 중입니다.
          </p>
        ) : loadedUser && form ? (
          <div className="mt-5 space-y-5">
            <dl className="grid gap-3 sm:grid-cols-2">
              <InfoItem label="ID" value={loadedUser.id} />
              <InfoItem label="생성일" value={formatDate(loadedUser.created_at)} />
              <InfoItem label="수정일" value={formatDate(loadedUser.updated_at)} />
              <InfoItem label="마지막 로그인" value={formatDate(loadedUser.last_login_at)} />
            </dl>

            {isAdmin ? (
              <div className="grid gap-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <TextField label="이메일" value={form.email} onChange={(value) => setForm({ ...form, email: value })} />
                  <TextField label="사용자명" value={form.username} onChange={(value) => setForm({ ...form, username: value })} />
                  <TextField label="표시 이름" value={form.display_name} onChange={(value) => setForm({ ...form, display_name: value })} />
                  <TextField label="비밀번호 해시" value={form.password_hash} onChange={(value) => setForm({ ...form, password_hash: value })} />
                  <label className="grid gap-1 text-sm font-bold">
                    권한
                    <select
                      className="h-11 rounded-lg border border-[var(--app-border)] bg-white px-3 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                      value={form.role}
                      onChange={(event) => setForm({ ...form, role: event.target.value as UserRole })}
                    >
                      {roleOptions.map((role) => (
                        <option key={role} value={role}>
                          {role}
                        </option>
                      ))}
                    </select>
                  </label>
                  <TextField label="상태" value={form.status} onChange={(value) => setForm({ ...form, status: value })} />
                  <TextField label="크레딧 잔액" value={form.credit_balance} onChange={(value) => setForm({ ...form, credit_balance: value })} />
                  <TextField label="대기 크레딧" value={form.credit_pending} onChange={(value) => setForm({ ...form, credit_pending: value })} />
                  <TextField label="출금 가능 크레딧" value={form.credit_withdrawable} onChange={(value) => setForm({ ...form, credit_withdrawable: value })} />
                  <TextField label="신뢰 점수" value={form.trust_score} onChange={(value) => setForm({ ...form, trust_score: value })} />
                  <TextField label="신뢰 등급" value={form.trust_tier} onChange={(value) => setForm({ ...form, trust_tier: value })} />
                  <TextField label="성공 작업 수" value={form.success_job_count} onChange={(value) => setForm({ ...form, success_job_count: value })} />
                  <TextField label="실패 작업 수" value={form.failed_job_count} onChange={(value) => setForm({ ...form, failed_job_count: value })} />
                  <TextField label="분쟁 작업 수" value={form.disputed_job_count} onChange={(value) => setForm({ ...form, disputed_job_count: value })} />
                  <TextField label="마지막 로그인" value={form.last_login_at} onChange={(value) => setForm({ ...form, last_login_at: value })} />
                </div>
                <label className="grid gap-1 text-sm font-bold">
                  메타데이터
                  <textarea
                    className="min-h-40 rounded-lg border border-[var(--app-border)] bg-white px-3 py-2 font-mono text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                    value={form.metadata_json}
                    onChange={(event) => setForm({ ...form, metadata_json: event.target.value })}
                  />
                </label>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <button
                    type="button"
                    className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-[#2c2c2c] px-4 text-sm font-extrabold text-white transition hover:bg-[#1f1f1f] disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={isSaving}
                    onClick={() => {
                      void saveUser();
                    }}
                  >
                    <Save className="h-4 w-4" aria-hidden="true" />
                    {isSaving ? '저장 중' : '저장'}
                  </button>
                  <DeleteButton isDeleting={isDeleting} onDelete={deleteUser} />
                </div>
              </div>
            ) : (
              <div className="rounded-lg border border-[#f2d8a8] bg-[#fff8e8] p-4">
                <p className="text-sm font-bold leading-6 text-[#73510d]">
                  자신의 계정 정보는 조회와 계정 삭제만 가능합니다.
                </p>
                <div className="mt-4">
                  <DeleteButton isDeleting={isDeleting} onDelete={deleteUser} />
                </div>
              </div>
            )}

            {isSelf ? (
              <div className="border-t border-[var(--app-border)] pt-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-xs font-black uppercase tracking-[0.14em] text-[var(--app-muted)]">
                      AccessKey
                    </p>
                    <h2 className="mt-1 text-xl font-black">API 접근 키</h2>
                  </div>
                  {canManageAccessKeys ? (
                    <button
                      type="button"
                      className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold transition hover:bg-[#f3f3f3] disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={isAccessKeyLoading}
                      onClick={() => {
                        void loadAccessKeys();
                      }}
                    >
                      <RefreshCw className="h-4 w-4" aria-hidden="true" />
                      {isAccessKeyLoading ? '새로고침 중' : '새로고침'}
                    </button>
                  ) : null}
                </div>

                {accessKeyError ? (
                  <p className="mt-4 rounded-lg border border-[#f2c4c4] bg-[var(--app-accent-soft)] px-3 py-2 text-sm font-bold text-[#9a2525]">
                    {accessKeyError}
                  </p>
                ) : null}

                {accessKeyMessage ? (
                  <p className="mt-4 rounded-lg border border-[#b9dfc1] bg-[#f1fff3] px-3 py-2 text-sm font-bold text-[#1f6f2e]">
                    {accessKeyMessage}
                  </p>
                ) : null}

                {!canManageAccessKeys ? (
                  <p className="mt-4 rounded-lg border border-[#f2d8a8] bg-[#fff8e8] px-3 py-2 text-sm font-bold text-[#73510d]">
                    AccessKey는 승인된 admin 또는 user 계정만 생성할 수 있습니다.
                  </p>
                ) : (
                  <>
                    {createdAccessKeySecret ? (
                      <div className="mt-4 rounded-lg border border-[#b9dfc1] bg-[#f1fff3] p-3">
                        <p className="text-sm font-black text-[#1f6f2e]">새 AccessKey</p>
                        <code className="mt-2 block break-all rounded-lg border border-[#b9dfc1] bg-white px-3 py-2 text-xs font-bold text-[#0f0f0f]">
                          {createdAccessKeySecret}
                        </code>
                        <button
                          type="button"
                          className="mt-3 inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-xs font-black transition hover:bg-[#f3f3f3]"
                          onClick={() => {
                            void copyCreatedAccessKeySecret();
                          }}
                        >
                          <Clipboard className="h-4 w-4" aria-hidden="true" />
                          복사
                        </button>
                      </div>
                    ) : null}

                    <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_220px_auto] lg:items-end">
                      <TextField
                        label="AccessKey 이름"
                        value={accessKeyName}
                        onChange={setAccessKeyName}
                      />
                      <label className="grid gap-1 text-sm font-bold">
                        만료일
                        <input
                          type="datetime-local"
                          className="h-11 rounded-lg border border-[var(--app-border)] bg-white px-3 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                          value={accessKeyExpiresAt}
                          onChange={(event) => setAccessKeyExpiresAt(event.target.value)}
                        />
                      </label>
                      <button
                        type="button"
                        className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-[#2c2c2c] px-4 text-sm font-extrabold text-white transition hover:bg-[#1f1f1f] disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={isAccessKeyCreating || !accessKeyName.trim()}
                        onClick={() => {
                          void createAccessKey();
                        }}
                      >
                        <KeyRound className="h-4 w-4" aria-hidden="true" />
                        {isAccessKeyCreating ? '생성 중' : '키 생성'}
                      </button>
                    </div>

                    <div className="mt-4 overflow-hidden rounded-lg border border-[var(--app-border)]">
                      <div className="overflow-x-auto">
                        <table className="w-full min-w-[900px] border-collapse text-left text-sm">
                          <thead className="bg-[#f7f7f7] text-xs font-black uppercase text-[var(--app-muted)]">
                            <tr>
                              <th className="px-3 py-3">이름</th>
                              <th className="px-3 py-3">Prefix</th>
                              <th className="px-3 py-3">상태</th>
                              <th className="px-3 py-3">생성일</th>
                              <th className="px-3 py-3">마지막 사용</th>
                              <th className="px-3 py-3">만료일</th>
                              <th className="px-3 py-3 text-right">작업</th>
                            </tr>
                          </thead>
                          <tbody>
                            {isAccessKeyLoading ? (
                              <tr>
                                <td className="px-3 py-6 text-center font-bold text-[var(--app-muted)]" colSpan={7}>
                                  AccessKey 목록을 불러오는 중입니다.
                                </td>
                              </tr>
                            ) : accessKeys.length === 0 ? (
                              <tr>
                                <td className="px-3 py-6 text-center font-bold text-[var(--app-muted)]" colSpan={7}>
                                  생성된 AccessKey가 없습니다.
                                </td>
                              </tr>
                            ) : (
                              accessKeys.map((item) => (
                                <tr key={item.id} className="border-t border-[var(--app-border)]">
                                  <td className="px-3 py-3 font-black">{item.name}</td>
                                  <td className="px-3 py-3 font-mono text-xs font-bold">{item.key_prefix}</td>
                                  <td className="px-3 py-3 font-bold">{item.status}</td>
                                  <td className="px-3 py-3 font-semibold text-[var(--app-muted)]">
                                    {formatDate(item.created_at)}
                                  </td>
                                  <td className="px-3 py-3 font-semibold text-[var(--app-muted)]">
                                    {formatDate(item.last_used_at)}
                                  </td>
                                  <td className="px-3 py-3 font-semibold text-[var(--app-muted)]">
                                    {formatDate(item.expires_at)}
                                  </td>
                                  <td className="px-3 py-3 text-right">
                                    <button
                                      type="button"
                                      className="inline-flex h-9 items-center gap-2 rounded-lg border border-[#b02c2c] bg-white px-3 text-xs font-black text-[#9a2525] transition hover:bg-[var(--app-accent-soft)] disabled:cursor-not-allowed disabled:opacity-50"
                                      disabled={item.status !== 'active' || revokingAccessKeyId === item.id}
                                      onClick={() => {
                                        void revokeAccessKey(item.id);
                                      }}
                                    >
                                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                                      {revokingAccessKeyId === item.id ? '폐기 중' : '폐기'}
                                    </button>
                                  </td>
                                </tr>
                              ))
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </>
                )}
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      <aside className="rounded-lg border border-[var(--app-border)] bg-white p-5 shadow-sm">
        <p className="text-xs font-black uppercase tracking-[0.14em] text-[var(--app-muted)]">
          Access
        </p>
        <h2 className="mt-1 text-xl font-black">권한 범위</h2>
        <p className="mt-4 text-sm font-semibold leading-6 text-[var(--app-muted)]">
          admin은 모든 사용자 데이터를 조회, 편집, 삭제할 수 있습니다. user와 unauthorized는 자신의 계정만 조회하고 삭제할 수 있습니다.
        </p>
        {isAdmin ? (
          <Link
            href="/users"
            className="mt-5 inline-flex h-11 w-full items-center justify-center rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
          >
            사용자 목록
          </Link>
        ) : null}
      </aside>
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-[var(--app-border)] bg-[#fafafa] p-3">
      <dt className="text-xs font-black uppercase text-[var(--app-muted)]">{label}</dt>
      <dd className="mt-1 truncate text-sm font-bold" title={value}>
        {value}
      </dd>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-1 text-sm font-bold">
      {label}
      <input
        className="h-11 rounded-lg border border-[var(--app-border)] bg-white px-3 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function DeleteButton({
  isDeleting,
  onDelete,
}: {
  isDeleting: boolean;
  onDelete: () => Promise<void>;
}) {
  return (
    <button
      type="button"
      className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-[#b02c2c] bg-white px-4 text-sm font-extrabold text-[#9a2525] transition hover:bg-[var(--app-accent-soft)] disabled:cursor-not-allowed disabled:opacity-50"
      disabled={isDeleting}
      onClick={() => {
        void onDelete();
      }}
    >
      <Trash2 className="h-4 w-4" aria-hidden="true" />
      {isDeleting ? '삭제 중' : '계정 삭제'}
    </button>
  );
}
