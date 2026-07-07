'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { Clipboard, KeyRound, RefreshCw, Save, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { api } from '../../../api/api';
import type { AccessKeyData, AccessKeyScope, LauncherSessionView, SlaveSessionData, UserAdminUpdate, UserData, UserRole } from '../../../api/types';
import { useAuthStore } from '../../../stores/authStore';
import { displayUserName, errorMessage, formatDate, nullableText } from '../../format';

type UserFormState = {
  email: string;
  username: string;
  display_name: string;
  role: UserRole;
  status: string;
};

const roleOptions: UserRole[] = ['admin', 'user', 'unauthorized'];

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
  const [launchers, setLaunchers] = useState<LauncherSessionView[]>([]);
  const [sessions, setSessions] = useState<SlaveSessionData[]>([]);
  const [tokens, setTokens] = useState<AccessKeyData[]>([]);
  const [tokenName, setTokenName] = useState('');
  const [tokenExpiresAt, setTokenExpiresAt] = useState('');
  const [tokenScopes, setTokenScopes] = useState<AccessKeyScope[]>(['client', 'launcher']);
  const [createdSecret, setCreatedSecret] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isTokenBusy, setIsTokenBusy] = useState(false);
  const [revokingTokenId, setRevokingTokenId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [tokenMessage, setTokenMessage] = useState<string | null>(null);

  const isAdmin = currentUser?.role === 'admin' || currentUser?.roles.includes('admin');
  const isSelf = Boolean(currentUser && userId && currentUser.id === userId);
  const canViewRuntime = Boolean(isAdmin || (isSelf && currentUser?.role === 'user'));
  const canManageTokens = Boolean(loadedUser && (isAdmin || isSelf) && loadedUser.role !== 'unauthorized' && loadedUser.status === 'active');

  const loadUser = useCallback(async () => {
    if (!authReady || !currentUser || !userId) {
      return;
    }
    setIsLoading(true);
    setError(null);
    setMessage(null);
    try {
      const nextUser = await api.users.get(userId);
      setLoadedUser(nextUser);
      setForm(userToForm(nextUser));
    } catch (loadError) {
      setError(errorMessage(loadError, '사용자 정보를 불러오지 못했습니다.'));
    } finally {
      setIsLoading(false);
    }
  }, [authReady, currentUser, userId]);

  const loadRelated = useCallback(async () => {
    if (!authReady || !currentUser || !userId || !canViewRuntime) {
      setLaunchers([]);
      setSessions([]);
      return;
    }
    try {
      const [nextLaunchers, nextSessions] = await Promise.all([
        api.launchers.list(isAdmin ? userId : undefined),
        api.slaveSessions.list(isAdmin ? userId : undefined),
      ]);
      setLaunchers(nextLaunchers);
      setSessions(nextSessions.slice(0, 10));
    } catch {
      setLaunchers([]);
      setSessions([]);
    }
  }, [authReady, canViewRuntime, currentUser, isAdmin, userId]);

  const loadTokens = useCallback(async () => {
    if (!authReady || !currentUser || !loadedUser || !userId || !canManageTokens) {
      setTokens([]);
      return;
    }
    setIsTokenBusy(true);
    setTokenError(null);
    try {
      setTokens(isAdmin && !isSelf ? await api.accessTokens.listForUser(userId) : await api.accessTokens.listMine());
    } catch (loadError) {
      setTokenError(errorMessage(loadError, 'Access Token 목록을 불러오지 못했습니다.'));
    } finally {
      setIsTokenBusy(false);
    }
  }, [authReady, canManageTokens, currentUser, isAdmin, isSelf, loadedUser, userId]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadUser();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadUser]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadRelated();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadRelated]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadTokens();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadTokens]);

  async function saveUser() {
    if (!userId || !form) {
      return;
    }
    setIsSaving(true);
    setError(null);
    setMessage(null);
    try {
      const updatedUser = await api.users.update(userId, buildPayload(form));
      setLoadedUser(updatedUser);
      setForm(userToForm(updatedUser));
      setMessage('저장했습니다.');
      if (isSelf) {
        await refreshUser();
      }
    } catch (saveError) {
      setError(errorMessage(saveError, '사용자 정보를 저장하지 못했습니다.'));
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
    try {
      await api.users.delete(userId);
      if (isSelf) {
        await refreshUser();
        router.push('/login');
      } else {
        router.push('/users');
      }
    } catch (deleteError) {
      setError(errorMessage(deleteError, '계정을 삭제하지 못했습니다.'));
    } finally {
      setIsDeleting(false);
    }
  }

  async function createToken() {
    if (!userId) {
      return;
    }
    setIsTokenBusy(true);
    setTokenError(null);
    setTokenMessage(null);
    setCreatedSecret(null);
    try {
      const payload = {
        name: requiredText(tokenName, 'Access Token 이름'),
        scopes: tokenScopes,
        expires_at: parseExpires(tokenExpiresAt),
      };
      const result = isAdmin && !isSelf
        ? await api.accessTokens.createForUser(userId, payload)
        : await api.accessTokens.createMine(payload);
      setTokens((items) => [result.access_key, ...items.filter((item) => item.id !== result.access_key.id)]);
      setTokenName('');
      setTokenExpiresAt('');
      setCreatedSecret(result.secret);
      setTokenMessage('Access Token을 생성했습니다. 원문 토큰은 지금만 확인할 수 있습니다.');
    } catch (createError) {
      setTokenError(errorMessage(createError, 'Access Token을 생성하지 못했습니다.'));
    } finally {
      setIsTokenBusy(false);
    }
  }

  async function revokeToken(tokenId: string) {
    if (!userId || !window.confirm('이 Access Token을 폐기할까요?')) {
      return;
    }
    setRevokingTokenId(tokenId);
    setTokenError(null);
    setTokenMessage(null);
    try {
      if (isAdmin && !isSelf) {
        await api.accessTokens.revokeForUser(userId, tokenId);
      } else {
        await api.accessTokens.revokeMine(tokenId);
      }
      setCreatedSecret(null);
      setTokenMessage('Access Token을 폐기했습니다.');
      await loadTokens();
    } catch (revokeError) {
      setTokenError(errorMessage(revokeError, 'Access Token을 폐기하지 못했습니다.'));
    } finally {
      setRevokingTokenId(null);
    }
  }

  async function copySecret() {
    if (!createdSecret) {
      return;
    }
    try {
      await navigator.clipboard.writeText(createdSecret);
      setTokenMessage('Access Token을 복사했습니다.');
    } catch {
      setTokenError('클립보드에 복사하지 못했습니다.');
    }
  }

  if (!authReady) {
    return <div className="centerState">사용자 정보를 확인 중입니다.</div>;
  }

  if (!currentUser) {
    return <NeedLogin />;
  }

  if (!isAdmin && !isSelf) {
    return <Forbidden currentUserId={currentUser.id} />;
  }

  return (
    <div className="pageWrap twoColumn">
      <section className="sectionStack">
        <div className="panel">
          <div className="pageHeader">
            <div>
              <p className="eyebrow">User</p>
              <h1>{loadedUser ? displayUserName(loadedUser) : '사용자'}</h1>
            </div>
            {loadedUser ? <span className="statusPill">{loadedUser.role} / {loadedUser.status}</span> : null}
          </div>

          {error ? <p className="message danger">{error}</p> : null}
          {message ? <p className="message success">{message}</p> : null}
          {isLoading ? <p className="message warn">사용자 정보를 불러오는 중입니다.</p> : null}

          {loadedUser && form ? (
            <div className="sectionStack">
              <dl className="detailList">
                <InfoItem label="ID" value={loadedUser.id} />
                <InfoItem label="생성일" value={formatDate(loadedUser.created_at)} />
                <InfoItem label="수정일" value={formatDate(loadedUser.updated_at)} />
              </dl>

              {isAdmin ? (
                <div className="formPanel sectionStack">
                  <h2>회원 정보</h2>
                  <div className="formGrid">
                    <TextField label="이메일" value={form.email} onChange={(value) => setForm({ ...form, email: value })} />
                    <TextField label="사용자명" value={form.username} onChange={(value) => setForm({ ...form, username: value })} />
                    <TextField label="표시 이름" value={form.display_name} onChange={(value) => setForm({ ...form, display_name: value })} />
                    <label className="field">
                      권한
                      <select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value as UserRole })}>
                        {roleOptions.map((role) => (
                          <option key={role} value={role}>{role}</option>
                        ))}
                      </select>
                    </label>
                    <TextField label="상태" value={form.status} onChange={(value) => setForm({ ...form, status: value })} />
                  </div>
                  <div className="rowActions" style={{ justifyContent: 'flex-start' }}>
                    <button
                      type="button"
                      className="button primaryButton"
                      disabled={isSaving}
                      onClick={() => {
                        void saveUser();
                      }}
                    >
                      <Save size={16} aria-hidden="true" />
                      {isSaving ? '저장 중' : '저장'}
                    </button>
                    <DeleteButton isDeleting={isDeleting} onDelete={deleteUser} />
                  </div>
                </div>
              ) : (
                <div className="message warn">
                  자신의 계정 정보는 조회와 계정 삭제만 가능합니다.
                  <div style={{ marginTop: 12 }}>
                    <DeleteButton isDeleting={isDeleting} onDelete={deleteUser} />
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>

        {loadedUser ? (
          <AccessTokenPanel
            canManage={canManageTokens}
            tokens={tokens}
            tokenName={tokenName}
            tokenExpiresAt={tokenExpiresAt}
            tokenScopes={tokenScopes}
            createdSecret={createdSecret}
            isBusy={isTokenBusy}
            revokingTokenId={revokingTokenId}
            error={tokenError}
            message={tokenMessage}
            onNameChange={setTokenName}
            onExpiresChange={setTokenExpiresAt}
            onScopesChange={setTokenScopes}
            onCreate={createToken}
            onRefresh={loadTokens}
            onRevoke={revokeToken}
            onCopy={copySecret}
          />
        ) : null}
      </section>

      <aside className="sectionStack">
        <section className="panel">
          <h2>접근 범위</h2>
          <p className="emptyText">
            admin은 모든 회원을 조회하고 편집할 수 있습니다. user와 unauthorized는 자신의 계정만 조회하고 삭제할 수 있습니다.
          </p>
          {isAdmin ? <Link href="/users" className="button fullButton" style={{ marginTop: 14 }}>회원 목록</Link> : null}
        </section>

        <RuntimePanel canView={canViewRuntime} launchers={launchers} sessions={sessions} />
      </aside>
    </div>
  );
}

function userToForm(user: UserData): UserFormState {
  return {
    email: user.email ?? '',
    username: user.username ?? '',
    display_name: user.display_name ?? '',
    role: user.role,
    status: user.status,
  };
}

function buildPayload(form: UserFormState): UserAdminUpdate {
  return {
    email: nullableText(form.email),
    username: nullableText(form.username),
    display_name: nullableText(form.display_name),
    role: form.role,
    status: requiredText(form.status, '상태'),
  };
}

function requiredText(value: string, label: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    throw new Error(`${label} 값을 입력해야 합니다.`);
  }
  return trimmed;
}

function parseExpires(value: string) {
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

function NeedLogin() {
  return (
    <div className="loginBox panel">
      <h1>로그인이 필요합니다</h1>
      <Link href="/login" className="button primaryButton fullButton" style={{ marginTop: 16 }}>로그인으로 이동</Link>
    </div>
  );
}

function Forbidden({ currentUserId }: { currentUserId: string }) {
  return (
    <div className="loginBox panel">
      <h1>접근할 수 없습니다</h1>
      <p className="message warn" style={{ marginTop: 16 }}>자신의 계정 정보만 확인할 수 있습니다.</p>
      <Link href={`/users/${currentUserId}`} className="button fullButton" style={{ marginTop: 14 }}>내 계정으로 이동</Link>
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="detailItem">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="field">
      {label}
      <input value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function DeleteButton({ isDeleting, onDelete }: { isDeleting: boolean; onDelete: () => Promise<void> }) {
  return (
    <button
      type="button"
      className="button dangerButton"
      disabled={isDeleting}
      onClick={() => {
        void onDelete();
      }}
    >
      <Trash2 size={16} aria-hidden="true" />
      {isDeleting ? '삭제 중' : '계정 삭제'}
    </button>
  );
}

function AccessTokenPanel({
  canManage,
  tokens,
  tokenName,
  tokenExpiresAt,
  tokenScopes,
  createdSecret,
  isBusy,
  revokingTokenId,
  error,
  message,
  onNameChange,
  onExpiresChange,
  onScopesChange,
  onCreate,
  onRefresh,
  onRevoke,
  onCopy,
}: {
  canManage: boolean;
  tokens: AccessKeyData[];
  tokenName: string;
  tokenExpiresAt: string;
  tokenScopes: AccessKeyScope[];
  createdSecret: string | null;
  isBusy: boolean;
  revokingTokenId: string | null;
  error: string | null;
  message: string | null;
  onNameChange: (value: string) => void;
  onExpiresChange: (value: string) => void;
  onScopesChange: (value: AccessKeyScope[]) => void;
  onCreate: () => Promise<void>;
  onRefresh: () => Promise<void>;
  onRevoke: (tokenId: string) => Promise<void>;
  onCopy: () => Promise<void>;
}) {
  function toggleScope(scope: AccessKeyScope) {
    const nextScopes = tokenScopes.includes(scope)
      ? tokenScopes.filter((item) => item !== scope)
      : [...tokenScopes, scope];
    onScopesChange(nextScopes);
  }

  return (
    <section className="panel sectionStack">
      <div className="toolbar">
        <div>
          <p className="eyebrow">Access Token</p>
          <h2>API 접근 토큰</h2>
        </div>
        {canManage ? (
          <button
            type="button"
            className="button smallButton"
            disabled={isBusy}
            onClick={() => {
              void onRefresh();
            }}
          >
            <RefreshCw size={15} aria-hidden="true" />
            새로고침
          </button>
        ) : null}
      </div>

      {!canManage ? <p className="message warn">Access Token은 활성화된 admin 또는 user 계정만 생성할 수 있습니다.</p> : null}
      {error ? <p className="message danger">{error}</p> : null}
      {message ? <p className="message success">{message}</p> : null}

      {createdSecret ? (
        <div className="secretBox">
          <strong>새 Access Token</strong>
          <code className="mono">{createdSecret}</code>
          <button
            type="button"
            className="button smallButton"
            onClick={() => {
              void onCopy();
            }}
          >
            <Clipboard size={15} aria-hidden="true" />
            복사
          </button>
        </div>
      ) : null}

      {canManage ? (
        <div className="formPanel sectionStack">
          <div className="formGrid">
            <TextField label="토큰 이름" value={tokenName} onChange={onNameChange} />
            <label className="field">
              만료일
              <input type="datetime-local" value={tokenExpiresAt} onChange={(event) => onExpiresChange(event.target.value)} />
            </label>
          </div>
          <div className="checkRow">
            {(['client', 'launcher'] as AccessKeyScope[]).map((scope) => (
              <label className="checkField" key={scope}>
                <input type="checkbox" checked={tokenScopes.includes(scope)} onChange={() => toggleScope(scope)} />
                {scope}
              </label>
            ))}
          </div>
          <button
            type="button"
            className="button primaryButton"
            disabled={isBusy || !tokenName.trim() || tokenScopes.length === 0}
            onClick={() => {
              void onCreate();
            }}
          >
            <KeyRound size={16} aria-hidden="true" />
            {isBusy ? '처리 중' : '토큰 생성'}
          </button>
        </div>
      ) : null}

      <div className="tableWrap">
        <div className="scrollTable">
          <table>
            <thead>
              <tr>
                <th>이름</th>
                <th>Prefix</th>
                <th>Scope</th>
                <th>상태</th>
                <th>생성일</th>
                <th style={{ textAlign: 'right' }}>작업</th>
              </tr>
            </thead>
            <tbody>
              {tokens.length === 0 ? (
                <tr>
                  <td colSpan={6} className="emptyText">생성된 Access Token이 없습니다.</td>
                </tr>
              ) : (
                tokens.map((token) => (
                  <tr key={token.id}>
                    <td>{token.name}</td>
                    <td className="mono">{token.key_prefix}</td>
                    <td>{token.scopes.join(', ') || '-'}</td>
                    <td><span className="statusPill">{token.status}</span></td>
                    <td>{formatDate(token.created_at)}</td>
                    <td>
                      <div className="rowActions">
                        <button
                          type="button"
                          className="button smallButton dangerButton"
                          disabled={!canManage || token.status !== 'active' || revokingTokenId === token.id}
                          onClick={() => {
                            void onRevoke(token.id);
                          }}
                        >
                          <Trash2 size={15} aria-hidden="true" />
                          {revokingTokenId === token.id ? '폐기 중' : '폐기'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function RuntimePanel({
  canView,
  launchers,
  sessions,
}: {
  canView: boolean;
  launchers: LauncherSessionView[];
  sessions: SlaveSessionData[];
}) {
  if (!canView) {
    return (
      <section className="panel">
        <h2>Launcher / SlaveSession</h2>
        <p className="message warn">승인된 user 또는 admin 계정에서만 런처와 세션 상태를 볼 수 있습니다.</p>
      </section>
    );
  }

  return (
    <section className="panel sectionStack">
      <h2>사용자별 런타임</h2>
      <div>
        <h3>Launcher</h3>
        <dl className="detailList">
          {launchers.slice(0, 5).map((launcher) => (
            <div className="detailItem" key={launcher.id}>
              <dt>{launcher.launcher_name} / {launcher.status}</dt>
              <dd>{launcher.slave_app_ids.join(', ') || '-'}</dd>
              <dd>{formatDate(launcher.last_heartbeat_at)}</dd>
            </div>
          ))}
          {launchers.length === 0 ? <p className="emptyText">연결된 Launcher가 없습니다.</p> : null}
        </dl>
      </div>
      <div>
        <h3>SlaveSession</h3>
        <dl className="detailList">
          {sessions.slice(0, 5).map((session) => (
            <div className="detailItem" key={session.id}>
              <dt>{session.slave_app_id} / {session.status}</dt>
              <dd className="mono">{session.id}</dd>
              <dd>{formatDate(session.created_at)}</dd>
            </div>
          ))}
          {sessions.length === 0 ? <p className="emptyText">SlaveSession이 없습니다.</p> : null}
        </dl>
      </div>
    </section>
  );
}
