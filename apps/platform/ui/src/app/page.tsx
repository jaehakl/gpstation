'use client';

import { useCallback, useEffect, useState } from 'react';
import { dbTables, type DbTableName } from '../api/api';
import type { UserData } from '../api/types';
import { useAuthStore } from '../stores/authStore';

const userPageSize = 100;

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

export default function HomePage() {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const startLogin = useAuthStore((state) => state.startLogin);
  const [users, setUsers] = useState<UserData[]>([]);
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);
  const [userError, setUserError] = useState<string | null>(null);
  const [deletingUserId, setDeletingUserId] = useState<string | null>(null);
  const isAdmin = user?.roles.includes('admin') || user?.role === 'admin';
  const tableEntries = Object.entries(dbTables) as Array<[DbTableName, (typeof dbTables)[DbTableName]]>;

  const loadUsers = useCallback(async () => {
    if (!isAdmin) {
      setUsers([]);
      return;
    }

    setIsLoadingUsers(true);
    setUserError(null);
    try {
      setUsers(await dbTables.User.getAllUsersAdmin(userPageSize, 0));
    } catch (error) {
      setUserError(error instanceof Error ? error.message : '사용자 목록을 불러오지 못했습니다.');
    } finally {
      setIsLoadingUsers(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    if (authReady && user && isAdmin) {
      const timeoutId = window.setTimeout(() => {
        void loadUsers();
      }, 0);

      return () => {
        window.clearTimeout(timeoutId);
      };
    }
  }, [authReady, isAdmin, loadUsers, user]);

  async function deleteUser(userId: string) {
    setDeletingUserId(userId);
    setUserError(null);
    try {
      await dbTables.User.deleteUserAdmin(userId);
      setUsers((items) => items.filter((item) => item.id !== userId));
    } catch (error) {
      setUserError(error instanceof Error ? error.message : '사용자를 삭제하지 못했습니다.');
    } finally {
      setDeletingUserId(null);
    }
  }

  if (!authReady) {
    return (
      <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center px-4 text-sm font-bold text-[var(--app-muted)]">
        사용자 정보를 확인 중입니다.
      </div>
    );
  }

  if (!user) {
    return (
      <div className="mx-auto flex min-h-[calc(100vh-3.5rem)] max-w-xl items-center px-4 py-10">
        <section className="w-full rounded-lg border border-[var(--app-border)] bg-white p-6 shadow-sm">
          <p className="text-xs font-black uppercase tracking-[0.14em] text-[var(--app-muted)]">
            GPStation Platform
          </p>
          <h1 className="mt-2 text-2xl font-black">계정 로그인이 필요합니다</h1>
          <p className="mt-3 text-sm font-semibold leading-6 text-[var(--app-muted)]">
            Google OAuth 로그인 후 계정 정보와 플랫폼 스키마를 확인할 수 있습니다.
          </p>
          <button
            type="button"
            className="mt-6 flex h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#b02c2c] bg-[var(--app-accent)] px-3 text-sm font-extrabold text-white transition hover:bg-[var(--app-accent-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            onClick={startLogin}
          >
            <span
              className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-white text-xs font-black text-[#4285f4]"
              aria-hidden="true"
            >
              G
            </span>
            Google로 로그인
          </button>
        </section>
      </div>
    );
  }

  return (
    <div className="mx-auto grid w-full max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:px-8">
      <div className="space-y-6">
        <section className="rounded-lg border border-[var(--app-border)] bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.14em] text-[var(--app-muted)]">
                Account
              </p>
              <h1 className="mt-1 text-2xl font-black">{displayUserName(user)}</h1>
            </div>
            <span className="inline-flex h-8 w-fit items-center rounded-full border border-[var(--app-border)] bg-[#fafafa] px-3 text-xs font-black">
              {user.role ?? 'user'} / {user.status ?? 'unknown'}
            </span>
          </div>

          <dl className="mt-5 grid gap-3 sm:grid-cols-2">
            <InfoItem label="ID" value={user.id} />
            <InfoItem label="이메일" value={user.email ?? '-'} />
            <InfoItem label="사용자명" value={user.username ?? '-'} />
            <InfoItem label="표시 이름" value={user.display_name ?? '-'} />
            <InfoItem label="생성일" value={formatDate(user.created_at)} />
            <InfoItem label="마지막 로그인" value={formatDate(user.last_login_at)} />
          </dl>
        </section>

        {isAdmin ? (
          <section className="rounded-lg border border-[var(--app-border)] bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.14em] text-[var(--app-muted)]">
                  Admin
                </p>
                <h2 className="mt-1 text-xl font-black">사용자 관리</h2>
              </div>
              <button
                type="button"
                className="h-10 rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                onClick={() => {
                  void loadUsers();
                }}
              >
                새로고침
              </button>
            </div>

            {userError ? (
              <p className="mt-4 rounded-lg border border-[#f2c4c4] bg-[var(--app-accent-soft)] px-3 py-2 text-sm font-bold text-[#9a2525]">
                {userError}
              </p>
            ) : null}

            <div className="mt-4 overflow-hidden rounded-lg border border-[var(--app-border)]">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] border-collapse text-left text-sm">
                  <thead className="bg-[#f7f7f7] text-xs font-black uppercase text-[var(--app-muted)]">
                    <tr>
                      <th className="px-3 py-3">사용자</th>
                      <th className="px-3 py-3">권한</th>
                      <th className="px-3 py-3">상태</th>
                      <th className="px-3 py-3">마지막 로그인</th>
                      <th className="px-3 py-3 text-right">작업</th>
                    </tr>
                  </thead>
                  <tbody>
                    {isLoadingUsers ? (
                      <tr>
                        <td className="px-3 py-6 text-center font-bold text-[var(--app-muted)]" colSpan={5}>
                          사용자 목록을 불러오는 중입니다.
                        </td>
                      </tr>
                    ) : users.length === 0 ? (
                      <tr>
                        <td className="px-3 py-6 text-center font-bold text-[var(--app-muted)]" colSpan={5}>
                          표시할 사용자가 없습니다.
                        </td>
                      </tr>
                    ) : (
                      users.map((item) => (
                        <tr key={item.id} className="border-t border-[var(--app-border)]">
                          <td className="px-3 py-3">
                            <p className="font-black">{displayUserName(item)}</p>
                            <p className="mt-1 max-w-[260px] truncate text-xs font-semibold text-[var(--app-muted)]">
                              {item.email ?? item.id}
                            </p>
                          </td>
                          <td className="px-3 py-3 font-bold">{item.role ?? item.roles[0] ?? '-'}</td>
                          <td className="px-3 py-3 font-bold">{item.status ?? '-'}</td>
                          <td className="px-3 py-3 font-semibold text-[var(--app-muted)]">
                            {formatDate(item.last_login_at)}
                          </td>
                          <td className="px-3 py-3 text-right">
                            <button
                              type="button"
                              className="h-9 rounded-lg border border-[#2e2d2d] bg-white px-3 text-xs font-black transition hover:bg-[#f3f3f3] disabled:cursor-not-allowed disabled:opacity-50"
                              disabled={item.id === user.id || deletingUserId === item.id}
                              onClick={() => {
                                void deleteUser(item.id);
                              }}
                            >
                              {deletingUserId === item.id ? '삭제 중' : '삭제'}
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        ) : null}
      </div>

      <aside className="rounded-lg border border-[var(--app-border)] bg-white p-5 shadow-sm">
        <p className="text-xs font-black uppercase tracking-[0.14em] text-[var(--app-muted)]">
          Schema
        </p>
        <h2 className="mt-1 text-xl font-black">플랫폼 테이블</h2>
        <div className="mt-4 grid gap-3">
          {tableEntries.map(([name, table]) => (
            <div key={name} className="rounded-lg border border-[var(--app-border)] bg-[#fafafa] p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-black">{table.label}</p>
                  <p className="truncate text-xs font-semibold text-[var(--app-muted)]">{name}</p>
                </div>
                <span className="shrink-0 rounded-full bg-white px-2 py-1 text-xs font-black text-[var(--app-muted)]">
                  {Object.keys(table.columns).length}
                </span>
              </div>
              <p className="mt-2 line-clamp-2 text-xs font-semibold leading-5 text-[var(--app-muted)]">
                {Object.entries(table.columns)
                  .slice(0, 5)
                  .map(([field, column]) => `${field}:${column.type}`)
                  .join(', ')}
              </p>
            </div>
          ))}
        </div>
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
