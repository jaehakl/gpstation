'use client';

import Link from 'next/link';
import { Cpu, LogIn, RefreshCw, User } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { dbTables, type DbTableName } from '../api/api';
import type { UserData, WorkerSessionData } from '../api/types';
import { useAuthStore } from '../stores/authStore';

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

function formatNumber(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') {
    return '-';
  }
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue.toLocaleString('ko-KR') : String(value);
}

export default function HomePage() {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const startLogin = useAuthStore((state) => state.startLogin);
  const tableEntries = Object.entries(dbTables) as Array<[DbTableName, (typeof dbTables)[DbTableName]]>;
  const [workerSessions, setWorkerSessions] = useState<WorkerSessionData[]>([]);
  const [isWorkerSessionLoading, setIsWorkerSessionLoading] = useState(false);
  const [workerSessionError, setWorkerSessionError] = useState<string | null>(null);
  const canViewWorkerSessions = Boolean(user?.role === 'admin' || user?.role === 'user' || user?.roles.includes('admin') || user?.roles.includes('user'));

  const loadWorkerSessions = useCallback(async () => {
    if (!canViewWorkerSessions) {
      setWorkerSessions([]);
      return;
    }

    setIsWorkerSessionLoading(true);
    setWorkerSessionError(null);
    try {
      setWorkerSessions(await dbTables.WorkerSession.listWorkerSessions());
    } catch (loadError) {
      setWorkerSessionError(loadError instanceof Error ? loadError.message : '워커 세션을 불러오지 못했습니다.');
    } finally {
      setIsWorkerSessionLoading(false);
    }
  }, [canViewWorkerSessions]);

  useEffect(() => {
    if (!authReady || !user || !canViewWorkerSessions) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      void loadWorkerSessions();
    }, 0);
    const intervalId = window.setInterval(() => {
      void loadWorkerSessions();
    }, 5000);

    return () => {
      window.clearTimeout(timeoutId);
      window.clearInterval(intervalId);
    };
  }, [authReady, canViewWorkerSessions, loadWorkerSessions, user]);

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
            Google OAuth 로그인 후 계정 정보와 플랫폼 콘솔을 확인할 수 있습니다.
          </p>
          <button
            type="button"
            className="mt-6 flex h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#b02c2c] bg-[var(--app-accent)] px-3 text-sm font-extrabold text-white transition hover:bg-[var(--app-accent-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            onClick={startLogin}
          >
            <LogIn className="h-4 w-4" aria-hidden="true" />
            Google로 로그인
          </button>
        </section>
      </div>
    );
  }

  return (
    <div className="mx-auto grid w-full max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:px-8">
      <div className="grid gap-6">
        <section className="rounded-lg border border-[var(--app-border)] bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.14em] text-[var(--app-muted)]">
                Account
              </p>
              <h1 className="mt-1 text-2xl font-black">{displayUserName(user)}</h1>
            </div>
            <span className="inline-flex h-8 w-fit items-center rounded-full border border-[var(--app-border)] bg-[#fafafa] px-3 text-xs font-black">
              {user.role ?? 'guest'} / {user.status ?? 'unknown'}
            </span>
          </div>

          {user.role === 'unauthorized' ? (
            <p className="mt-4 rounded-lg border border-[#f2d8a8] bg-[#fff8e8] px-3 py-2 text-sm font-bold text-[#73510d]">
              관리자 승인 전 계정입니다. 내 계정 조회와 계정 삭제만 사용할 수 있습니다.
            </p>
          ) : null}

          <dl className="mt-5 grid gap-3 sm:grid-cols-2">
            <InfoItem label="ID" value={user.id} />
            <InfoItem label="이메일" value={user.email ?? '-'} />
            <InfoItem label="사용자명" value={user.username ?? '-'} />
            <InfoItem label="표시 이름" value={user.display_name ?? '-'} />
            <InfoItem label="생성일" value={formatDate(user.created_at)} />
            <InfoItem label="마지막 로그인" value={formatDate(user.last_login_at)} />
          </dl>

          <Link
            href={`/users/${user.id}`}
            className="mt-5 inline-flex h-11 items-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-4 text-sm font-extrabold transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
          >
            <User className="h-4 w-4" aria-hidden="true" />
            내 계정
          </Link>
        </section>

        {canViewWorkerSessions ? (
          <section className="rounded-lg border border-[var(--app-border)] bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.14em] text-[var(--app-muted)]">
                  Workers
                </p>
                <h2 className="mt-1 flex items-center gap-2 text-xl font-black">
                  <Cpu className="h-5 w-5" aria-hidden="true" />
                  워커 GPU 상태
                </h2>
              </div>
              <button
                type="button"
                className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold transition hover:bg-[#f3f3f3] disabled:cursor-not-allowed disabled:opacity-50"
                disabled={isWorkerSessionLoading}
                onClick={() => {
                  void loadWorkerSessions();
                }}
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                {isWorkerSessionLoading ? '새로고침 중' : '새로고침'}
              </button>
            </div>

            {workerSessionError ? (
              <p className="mt-4 rounded-lg border border-[#f2c4c4] bg-[var(--app-accent-soft)] px-3 py-2 text-sm font-bold text-[#9a2525]">
                {workerSessionError}
              </p>
            ) : null}

            <div className="mt-4 overflow-hidden rounded-lg border border-[var(--app-border)]">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] border-collapse text-left text-sm">
                  <thead className="bg-[#f7f7f7] text-xs font-black uppercase text-[var(--app-muted)]">
                    <tr>
                      <th className="px-3 py-3">상태</th>
                      <th className="px-3 py-3">GPU</th>
                      <th className="px-3 py-3">VRAM</th>
                      <th className="px-3 py-3">온도</th>
                      <th className="px-3 py-3">사용률</th>
                      <th className="px-3 py-3">마지막 Heartbeat</th>
                    </tr>
                  </thead>
                  <tbody>
                    {isWorkerSessionLoading && workerSessions.length === 0 ? (
                      <tr>
                        <td className="px-3 py-6 text-center font-bold text-[var(--app-muted)]" colSpan={6}>
                          워커 상태를 불러오는 중입니다.
                        </td>
                      </tr>
                    ) : workerSessions.length === 0 ? (
                      <tr>
                        <td className="px-3 py-6 text-center font-bold text-[var(--app-muted)]" colSpan={6}>
                          연결된 워커가 없습니다.
                        </td>
                      </tr>
                    ) : (
                      workerSessions.map((session) => (
                        <tr key={session.id} className="border-t border-[var(--app-border)]">
                          <td className="px-3 py-3 font-black">{session.status}</td>
                          <td className="px-3 py-3">
                            <p className="font-black">{session.gpu_name ?? 'GPU 없음'}</p>
                            <p className="mt-1 text-xs font-semibold text-[var(--app-muted)]">
                              {session.client_version ?? '-'} / {session.gpu_vendor ?? '-'}
                            </p>
                          </td>
                          <td className="px-3 py-3 font-semibold text-[var(--app-muted)]">
                            {formatNumber(session.vram_available_mb)} / {formatNumber(session.vram_total_mb)} MB
                          </td>
                          <td className="px-3 py-3 font-semibold text-[var(--app-muted)]">
                            {formatNumber(session.gpu_temperature_c)} C
                          </td>
                          <td className="px-3 py-3 font-semibold text-[var(--app-muted)]">
                            {formatNumber(session.gpu_utilization_pct)} %
                          </td>
                          <td className="px-3 py-3 font-semibold text-[var(--app-muted)]">
                            {formatDate(session.last_heartbeat_at)}
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
