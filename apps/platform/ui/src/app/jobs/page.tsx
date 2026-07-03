'use client';

import Link from 'next/link';
import { Eye, Plus, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { dbTables } from '../../api/api';
import type { JobData, UserData } from '../../api/types';
import { useAuthStore } from '../../stores/authStore';

const jobPageSize = 100;

function canUseJobs(user: UserData | null) {
  return Boolean(
    user?.roles.includes('admin') ||
      user?.roles.includes('user') ||
      user?.role === 'admin' ||
      user?.role === 'user',
  );
}

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

function shortId(value: string | null | undefined) {
  if (!value) {
    return '-';
  }
  return value.length > 12 ? `${value.slice(0, 8)}...${value.slice(-4)}` : value;
}

export default function JobsPage() {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const [jobs, setJobs] = useState<JobData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isAllowed = canUseJobs(user);

  const loadJobs = useCallback(async () => {
    if (!isAllowed) {
      setJobs([]);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      setJobs(await dbTables.Job.listJobs(jobPageSize, 0));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '작업 목록을 불러오지 못했습니다.');
    } finally {
      setIsLoading(false);
    }
  }, [isAllowed]);

  useEffect(() => {
    if (!authReady || !isAllowed) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      void loadJobs();
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [authReady, isAllowed, loadJobs]);

  if (!authReady) {
    return (
      <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center px-4 text-sm font-bold text-[var(--app-muted)]">
        사용자 정보를 확인 중입니다.
      </div>
    );
  }

  if (!user) {
    return <JobsAccessMessage title="로그인이 필요합니다" actionHref="/login" actionLabel="로그인으로 이동" />;
  }

  if (!isAllowed) {
    return <JobsAccessMessage title="접근할 수 없습니다" actionHref="/" actionLabel="홈으로 이동" />;
  }

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 lg:px-8">
      <section className="rounded-lg border border-[var(--app-border)] bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.14em] text-[var(--app-muted)]">
              Jobs
            </p>
            <h1 className="mt-1 text-2xl font-black">작업</h1>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Link
              href="/jobs/new"
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-[#2c2c2c] px-3 text-sm font-extrabold text-white transition hover:bg-[#1f1f1f] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              새 작업 요청
            </Link>
            <button
              type="button"
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:opacity-50"
              disabled={isLoading}
              onClick={() => {
                void loadJobs();
              }}
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              {isLoading ? '새로고침 중' : '새로고침'}
            </button>
          </div>
        </div>

        {error ? (
          <p className="mt-4 rounded-lg border border-[#f2c4c4] bg-[var(--app-accent-soft)] px-3 py-2 text-sm font-bold text-[#9a2525]">
            {error}
          </p>
        ) : null}

        <div className="mt-4 overflow-hidden rounded-lg border border-[var(--app-border)]">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] border-collapse text-left text-sm">
              <thead className="bg-[#f7f7f7] text-xs font-black uppercase text-[var(--app-muted)]">
                <tr>
                  <th className="px-3 py-3">상태</th>
                  <th className="px-3 py-3">작업 유형</th>
                  <th className="px-3 py-3">요청자</th>
                  <th className="px-3 py-3">워커 세션</th>
                  <th className="px-3 py-3">생성일</th>
                  <th className="px-3 py-3">수정일</th>
                  <th className="px-3 py-3 text-right">작업</th>
                </tr>
              </thead>
              <tbody>
                {isLoading && jobs.length === 0 ? (
                  <tr>
                    <td className="px-3 py-6 text-center font-bold text-[var(--app-muted)]" colSpan={7}>
                      작업 목록을 불러오는 중입니다.
                    </td>
                  </tr>
                ) : jobs.length === 0 ? (
                  <tr>
                    <td className="px-3 py-6 text-center font-bold text-[var(--app-muted)]" colSpan={7}>
                      표시할 작업이 없습니다.
                    </td>
                  </tr>
                ) : (
                  jobs.map((job) => (
                    <tr key={job.id} className="border-t border-[var(--app-border)]">
                      <td className="px-3 py-3 font-black">{job.status}</td>
                      <td className="px-3 py-3">
                        <p className="font-black">{job.task_type}</p>
                        <p className="mt-1 font-mono text-xs font-semibold text-[var(--app-muted)]">
                          {shortId(job.id)}
                        </p>
                      </td>
                      <td className="px-3 py-3 font-mono text-xs font-bold text-[var(--app-muted)]">
                        {shortId(job.requester_user_id)}
                      </td>
                      <td className="px-3 py-3 font-mono text-xs font-bold text-[var(--app-muted)]">
                        {shortId(job.worker_session_id)}
                      </td>
                      <td className="px-3 py-3 font-semibold text-[var(--app-muted)]">
                        {formatDate(job.created_at)}
                      </td>
                      <td className="px-3 py-3 font-semibold text-[var(--app-muted)]">
                        {formatDate(job.updated_at)}
                      </td>
                      <td className="px-3 py-3 text-right">
                        <Link
                          href={`/jobs/${job.id}`}
                          className="inline-flex h-9 items-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-xs font-black transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                        >
                          <Eye className="h-4 w-4" aria-hidden="true" />
                          상세
                        </Link>
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

function JobsAccessMessage({
  title,
  actionHref,
  actionLabel,
}: {
  title: string;
  actionHref: string;
  actionLabel: string;
}) {
  return (
    <div className="mx-auto flex min-h-[calc(100vh-3.5rem)] max-w-xl items-center px-4 py-10">
      <section className="w-full rounded-lg border border-[var(--app-border)] bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-black">{title}</h1>
        <Link
          href={actionHref}
          className="mt-5 inline-flex h-11 w-full items-center justify-center rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
        >
          {actionLabel}
        </Link>
      </section>
    </div>
  );
}
