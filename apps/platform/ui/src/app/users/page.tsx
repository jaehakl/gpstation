'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Eye, RefreshCw, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { dbTables } from '../../api/api';
import type { UserData } from '../../api/types';
import { AdminGate } from '../AdminGate';
import { useAuthStore } from '../../stores/authStore';

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

export default function UsersPage() {
  return (
    <AdminGate>
      <UsersPageContent />
    </AdminGate>
  );
}

function UsersPageContent() {
  const router = useRouter();
  const currentUser = useAuthStore((state) => state.user);
  const refreshUser = useAuthStore((state) => state.refreshUser);
  const [users, setUsers] = useState<UserData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingUserId, setDeletingUserId] = useState<string | null>(null);

  const loadUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setUsers(await dbTables.User.listUsers(userPageSize, 0));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '사용자 목록을 불러오지 못했습니다.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadUsers();
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [loadUsers]);

  async function deleteUser(userId: string) {
    if (!window.confirm('이 사용자를 삭제할까요?')) {
      return;
    }

    setDeletingUserId(userId);
    setError(null);
    try {
      await dbTables.User.deleteUser(userId);
      if (currentUser?.id === userId) {
        await refreshUser();
        router.push('/login');
        return;
      }
      setUsers((items) => items.filter((item) => item.id !== userId));
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : '사용자를 삭제하지 못했습니다.');
    } finally {
      setDeletingUserId(null);
    }
  }

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 lg:px-8">
      <section className="rounded-lg border border-[var(--app-border)] bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.14em] text-[var(--app-muted)]">
              Admin
            </p>
            <h1 className="mt-1 text-2xl font-black">사용자 관리</h1>
          </div>
          <button
            type="button"
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            onClick={() => {
              void loadUsers();
            }}
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            새로고침
          </button>
        </div>

        {error ? (
          <p className="mt-4 rounded-lg border border-[#f2c4c4] bg-[var(--app-accent-soft)] px-3 py-2 text-sm font-bold text-[#9a2525]">
            {error}
          </p>
        ) : null}

        <div className="mt-4 overflow-hidden rounded-lg border border-[var(--app-border)]">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] border-collapse text-left text-sm">
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
                {isLoading ? (
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
                        <p className="mt-1 max-w-[280px] truncate text-xs font-semibold text-[var(--app-muted)]">
                          {item.email ?? item.id}
                        </p>
                      </td>
                      <td className="px-3 py-3 font-bold">{item.role ?? '-'}</td>
                      <td className="px-3 py-3 font-bold">{item.status ?? '-'}</td>
                      <td className="px-3 py-3 font-semibold text-[var(--app-muted)]">
                        {formatDate(item.last_login_at)}
                      </td>
                      <td className="px-3 py-3 text-right">
                        <div className="flex justify-end gap-2">
                          <Link
                            href={`/users/${item.id}`}
                            className="inline-flex h-9 items-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-xs font-black transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                          >
                            <Eye className="h-4 w-4" aria-hidden="true" />
                            상세
                          </Link>
                          <button
                            type="button"
                            className="inline-flex h-9 items-center gap-2 rounded-lg border border-[#b02c2c] bg-white px-3 text-xs font-black text-[#9a2525] transition hover:bg-[var(--app-accent-soft)] disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={deletingUserId === item.id}
                            onClick={() => {
                              void deleteUser(item.id);
                            }}
                          >
                            <Trash2 className="h-4 w-4" aria-hidden="true" />
                            {deletingUserId === item.id ? '삭제 중' : '삭제'}
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
    </div>
  );
}
