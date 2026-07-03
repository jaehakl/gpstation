'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { useState } from 'react';
import { dbTables } from '../../../api/api';
import type { JobTaskType, UserData } from '../../../api/types';
import { useAuthStore } from '../../../stores/authStore';
import { EmbeddingRequestForm } from './EmbeddingRequestForm';
import { LlmSingleRequestForm } from './LlmSingleRequestForm';
import { SdxlT2IRequestForm } from './SdxlT2IRequestForm';

const taskTypes: JobTaskType[] = ['llm_single', 'sdxl_t2i', 'embedding'];

function canUseJobs(user: UserData | null) {
  return Boolean(
    user?.roles.includes('admin') ||
      user?.roles.includes('user') ||
      user?.role === 'admin' ||
      user?.role === 'user',
  );
}

export default function NewJobPage() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const [taskType, setTaskType] = useState<JobTaskType>('llm_single');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isAllowed = canUseJobs(user);

  async function createJob(requestJson: Record<string, unknown>) {
    setIsCreating(true);
    setError(null);
    try {
      const result = await dbTables.Job.createJob({
        task_type: taskType,
        request_json: requestJson,
      });
      router.push(`/jobs/${result.job_id}`);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : '작업 요청을 생성하지 못했습니다.');
    } finally {
      setIsCreating(false);
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
    return <JobsAccessMessage title="로그인이 필요합니다" actionHref="/login" actionLabel="로그인으로 이동" />;
  }

  if (!isAllowed) {
    return <JobsAccessMessage title="접근할 수 없습니다" actionHref="/" actionLabel="홈으로 이동" />;
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 lg:px-8">
      <section className="rounded-lg border border-[var(--app-border)] bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.14em] text-[var(--app-muted)]">
              Jobs
            </p>
            <h1 className="mt-1 text-2xl font-black">새 작업 요청</h1>
          </div>
          <Link
            href="/jobs"
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            목록
          </Link>
        </div>

        {error ? (
          <p className="mt-4 rounded-lg border border-[#f2c4c4] bg-[var(--app-accent-soft)] px-3 py-2 text-sm font-bold text-[#9a2525]">
            {error}
          </p>
        ) : null}

        <div className="mt-5 grid gap-5">
          <div className="flex flex-wrap gap-2">
            {taskTypes.map((item) => (
              <button
                key={item}
                type="button"
                className={[
                  'h-10 rounded-lg border px-4 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                  taskType === item
                    ? 'border-[#404040] bg-[#2c2c2c] text-white'
                    : 'border-[#2e2d2d] bg-white hover:bg-[#f3f3f3]',
                ].join(' ')}
                onClick={() => {
                  setTaskType(item);
                  setError(null);
                }}
              >
                {item}
              </button>
            ))}
          </div>

          {taskType === 'llm_single' ? (
            <LlmSingleRequestForm
              disabled={isCreating}
              onError={setError}
              onSubmit={(requestJson) => {
                void createJob(requestJson);
              }}
            />
          ) : null}
          {taskType === 'sdxl_t2i' ? (
            <SdxlT2IRequestForm
              disabled={isCreating}
              onError={setError}
              onSubmit={(requestJson) => {
                void createJob(requestJson);
              }}
            />
          ) : null}
          {taskType === 'embedding' ? (
            <EmbeddingRequestForm
              disabled={isCreating}
              onError={setError}
              onSubmit={(requestJson) => {
                void createJob(requestJson);
              }}
            />
          ) : null}

          <Link
            href="/jobs"
            className="inline-flex h-11 w-fit items-center justify-center rounded-lg border border-[#2e2d2d] bg-white px-4 text-sm font-extrabold transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
          >
            취소
          </Link>
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
