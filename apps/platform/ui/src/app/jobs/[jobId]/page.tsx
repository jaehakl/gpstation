'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, Plus, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { dbTables } from '../../../api/api';
import type { JobDetailData, UserData, WorkerSessionData } from '../../../api/types';
import { useAuthStore } from '../../../stores/authStore';

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

function formatValue(value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined || value === '') {
    return '-';
  }
  return String(value);
}

function shortId(value: string | null | undefined) {
  if (!value) {
    return '-';
  }
  return value.length > 16 ? `${value.slice(0, 10)}...${value.slice(-6)}` : value;
}

function jsonText(value: Record<string, unknown> | undefined) {
  return JSON.stringify(value ?? {}, null, 2);
}

export default function JobDetailPage() {
  const params = useParams<{ jobId?: string | string[] }>();
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const jobIdParam = params.jobId;
  const jobId = Array.isArray(jobIdParam) ? jobIdParam[0] : jobIdParam;
  const [detail, setDetail] = useState<JobDetailData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isAllowed = canUseJobs(user);

  const loadJob = useCallback(async () => {
    if (!jobId || !isAllowed) {
      setDetail(null);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      setDetail(await dbTables.Job.getJob(jobId));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '작업 상세를 불러오지 못했습니다.');
    } finally {
      setIsLoading(false);
    }
  }, [isAllowed, jobId]);

  useEffect(() => {
    if (!authReady || !isAllowed) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      void loadJob();
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [authReady, isAllowed, loadJob]);

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
    <div className="mx-auto grid w-full max-w-7xl gap-6 px-4 py-6 lg:px-8">
      <section className="rounded-lg border border-[var(--app-border)] bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-black uppercase tracking-[0.14em] text-[var(--app-muted)]">
              Job
            </p>
            <h1 className="mt-1 truncate text-2xl font-black">
              {detail ? detail.job.task_type : shortId(jobId)}
            </h1>
            <p className="mt-1 break-all font-mono text-xs font-semibold text-[var(--app-muted)]">
              {jobId ?? '-'}
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Link
              href="/jobs"
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              목록
            </Link>
            <Link
              href="/jobs/new"
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              새 요청
            </Link>
            <button
              type="button"
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:opacity-50"
              disabled={isLoading}
              onClick={() => {
                void loadJob();
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

        {isLoading && !detail ? (
          <p className="mt-5 rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa] px-4 py-8 text-center text-sm font-bold text-[var(--app-muted)]">
            작업 상세를 불러오는 중입니다.
          </p>
        ) : null}

        {detail ? <JobSummary detail={detail} /> : null}
      </section>

      {detail ? (
        <>
          <WorkerSessionSection workerSession={detail.worker_session ?? null} />
          <MessagesSection detail={detail} />
          <MessagePartsSection detail={detail} />
          <StoredObjectsSection detail={detail} />
        </>
      ) : null}
    </div>
  );
}

function JobSummary({ detail }: { detail: JobDetailData }) {
  const job = detail.job;

  return (
    <div className="mt-5 grid gap-5">
      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <InfoItem label="상태" value={job.status} />
        <InfoItem label="작업 유형" value={job.task_type} />
        <InfoItem label="요청자" value={job.requester_user_id} />
        <InfoItem label="워커 사용자" value={job.worker_user_id ?? '-'} />
        <InfoItem label="워커 세션" value={job.worker_session_id ?? '-'} />
        <InfoItem label="우선순위" value={formatValue(job.priority)} />
        <InfoItem label="재시도" value={`${job.retry_count} / ${job.max_retries}`} />
        <InfoItem label="필요 모델" value={job.required_model_id ?? '-'} />
        <InfoItem label="필요 VRAM" value={formatValue(job.required_vram_gb)} />
        <InfoItem label="가격 한도" value={formatValue(job.price_limit_credit)} />
        <InfoItem label="예상 비용" value={formatValue(job.estimated_cost_credit)} />
        <InfoItem label="최종 비용" value={formatValue(job.final_cost_credit)} />
        <InfoItem label="시작일" value={formatDate(job.started_at)} />
        <InfoItem label="완료일" value={formatDate(job.completed_at)} />
        <InfoItem label="실패일" value={formatDate(job.failed_at)} />
        <InfoItem label="취소일" value={formatDate(job.cancelled_at)} />
        <InfoItem label="생성일" value={formatDate(job.created_at)} />
        <InfoItem label="수정일" value={formatDate(job.updated_at)} />
        <InfoItem label="오류 코드" value={job.error_code ?? '-'} />
        <InfoItem label="오류 메시지" value={job.error_message ?? '-'} />
      </dl>
      <JsonPanel title="metadata_json" value={job.metadata_json} />
    </div>
  );
}

function WorkerSessionSection({ workerSession }: { workerSession: WorkerSessionData | null }) {
  return (
    <section className="rounded-lg border border-[var(--app-border)] bg-white p-5 shadow-sm">
      <SectionTitle eyebrow="Worker" title="워커 세션" />
      {workerSession ? (
        <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <InfoItem label="ID" value={workerSession.id} />
          <InfoItem label="사용자" value={workerSession.user_id} />
          <InfoItem label="상태" value={workerSession.status} />
          <InfoItem label="작업 수락" value={workerSession.accepting_jobs ? 'true' : 'false'} />
          <InfoItem label="GPU" value={workerSession.gpu_name ?? '-'} />
          <InfoItem label="GPU 벤더" value={workerSession.gpu_vendor ?? '-'} />
          <InfoItem label="VRAM 총량" value={formatValue(workerSession.vram_total_mb)} />
          <InfoItem label="VRAM 가용" value={formatValue(workerSession.vram_available_mb)} />
          <InfoItem label="마지막 Heartbeat" value={formatDate(workerSession.last_heartbeat_at)} />
          <InfoItem label="연결일" value={formatDate(workerSession.connected_at)} />
          <InfoItem label="연결 종료일" value={formatDate(workerSession.disconnected_at)} />
          <InfoItem label="현재 작업" value={workerSession.current_job_id ?? '-'} />
        </dl>
      ) : (
        <EmptyState text="연결된 워커 세션이 없습니다." />
      )}
    </section>
  );
}

function MessagesSection({ detail }: { detail: JobDetailData }) {
  return (
    <section className="rounded-lg border border-[var(--app-border)] bg-white p-5 shadow-sm">
      <SectionTitle eyebrow="Messages" title="작업 메시지" />
      <div className="mt-4 overflow-hidden rounded-lg border border-[var(--app-border)]">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px] border-collapse text-left text-sm">
            <thead className="bg-[#f7f7f7] text-xs font-black uppercase text-[var(--app-muted)]">
              <tr>
                <th className="px-3 py-3">역할</th>
                <th className="px-3 py-3">종류</th>
                <th className="px-3 py-3">상태</th>
                <th className="px-3 py-3">작성자</th>
                <th className="px-3 py-3">생성일</th>
                <th className="px-3 py-3">metadata_json</th>
              </tr>
            </thead>
            <tbody>
              {detail.messages.length === 0 ? (
                <tr>
                  <td className="px-3 py-6 text-center font-bold text-[var(--app-muted)]" colSpan={6}>
                    메시지가 없습니다.
                  </td>
                </tr>
              ) : (
                detail.messages.map((message) => (
                  <tr key={message.id} className="border-t border-[var(--app-border)] align-top">
                    <td className="px-3 py-3 font-black">{message.role}</td>
                    <td className="px-3 py-3 font-bold">{message.kind}</td>
                    <td className="px-3 py-3 font-bold">{message.status}</td>
                    <td className="px-3 py-3 font-mono text-xs font-bold text-[var(--app-muted)]">
                      {shortId(message.created_by_user_id)}
                    </td>
                    <td className="px-3 py-3 font-semibold text-[var(--app-muted)]">
                      {formatDate(message.created_at)}
                    </td>
                    <td className="px-3 py-3">
                      <CodeBlock value={jsonText(message.metadata_json)} />
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

function MessagePartsSection({ detail }: { detail: JobDetailData }) {
  return (
    <section className="rounded-lg border border-[var(--app-border)] bg-white p-5 shadow-sm">
      <SectionTitle eyebrow="Parts" title="메시지 파트" />
      <div className="mt-4 overflow-hidden rounded-lg border border-[var(--app-border)]">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] border-collapse text-left text-sm">
            <thead className="bg-[#f7f7f7] text-xs font-black uppercase text-[var(--app-muted)]">
              <tr>
                <th className="px-3 py-3">메시지</th>
                <th className="px-3 py-3">이름</th>
                <th className="px-3 py-3">파트 유형</th>
                <th className="px-3 py-3">저장 객체</th>
                <th className="px-3 py-3">정렬</th>
                <th className="px-3 py-3">필수</th>
                <th className="px-3 py-3">metadata_json</th>
              </tr>
            </thead>
            <tbody>
              {detail.message_parts.length === 0 ? (
                <tr>
                  <td className="px-3 py-6 text-center font-bold text-[var(--app-muted)]" colSpan={7}>
                    메시지 파트가 없습니다.
                  </td>
                </tr>
              ) : (
                detail.message_parts.map((part) => (
                  <tr key={part.id} className="border-t border-[var(--app-border)] align-top">
                    <td className="px-3 py-3 font-mono text-xs font-bold text-[var(--app-muted)]">
                      {shortId(part.message_id)}
                    </td>
                    <td className="px-3 py-3 font-bold">{part.name ?? '-'}</td>
                    <td className="px-3 py-3 font-bold">{part.part_type}</td>
                    <td className="px-3 py-3 font-mono text-xs font-bold text-[var(--app-muted)]">
                      {shortId(part.object_id)}
                    </td>
                    <td className="px-3 py-3 font-semibold text-[var(--app-muted)]">{part.sort_order}</td>
                    <td className="px-3 py-3 font-semibold text-[var(--app-muted)]">
                      {part.required ? 'true' : 'false'}
                    </td>
                    <td className="px-3 py-3">
                      <CodeBlock value={jsonText(part.metadata_json)} />
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

function StoredObjectsSection({ detail }: { detail: JobDetailData }) {
  return (
    <section className="rounded-lg border border-[var(--app-border)] bg-white p-5 shadow-sm">
      <SectionTitle eyebrow="Objects" title="저장 객체" />
      <div className="mt-4 overflow-hidden rounded-lg border border-[var(--app-border)]">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1040px] border-collapse text-left text-sm">
            <thead className="bg-[#f7f7f7] text-xs font-black uppercase text-[var(--app-muted)]">
              <tr>
                <th className="px-3 py-3">객체</th>
                <th className="px-3 py-3">유형</th>
                <th className="px-3 py-3">저장소</th>
                <th className="px-3 py-3">URI</th>
                <th className="px-3 py-3">MIME</th>
                <th className="px-3 py-3">크기</th>
                <th className="px-3 py-3">SHA-256</th>
                <th className="px-3 py-3">metadata_json</th>
              </tr>
            </thead>
            <tbody>
              {detail.stored_objects.length === 0 ? (
                <tr>
                  <td className="px-3 py-6 text-center font-bold text-[var(--app-muted)]" colSpan={8}>
                    저장 객체가 없습니다.
                  </td>
                </tr>
              ) : (
                detail.stored_objects.map((object) => (
                  <tr key={object.id} className="border-t border-[var(--app-border)] align-top">
                    <td className="px-3 py-3 font-mono text-xs font-bold text-[var(--app-muted)]">
                      {shortId(object.id)}
                    </td>
                    <td className="px-3 py-3 font-bold">{object.object_type}</td>
                    <td className="px-3 py-3 font-bold">{object.storage_backend}</td>
                    <td className="max-w-[240px] break-all px-3 py-3 font-semibold text-[var(--app-muted)]">
                      {object.uri ?? '-'}
                    </td>
                    <td className="px-3 py-3 font-semibold text-[var(--app-muted)]">
                      {object.mime_type ?? '-'}
                    </td>
                    <td className="px-3 py-3 font-semibold text-[var(--app-muted)]">
                      {formatValue(object.size_bytes)}
                    </td>
                    <td className="max-w-[200px] break-all px-3 py-3 font-mono text-xs font-bold text-[var(--app-muted)]">
                      {object.sha256 ?? '-'}
                    </td>
                    <td className="px-3 py-3">
                      <CodeBlock value={jsonText(object.metadata_json)} />
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

function SectionTitle({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div>
      <p className="text-xs font-black uppercase tracking-[0.14em] text-[var(--app-muted)]">
        {eyebrow}
      </p>
      <h2 className="mt-1 text-xl font-black">{title}</h2>
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-[var(--app-border)] bg-[#fafafa] p-3">
      <dt className="text-xs font-black uppercase text-[var(--app-muted)]">{label}</dt>
      <dd className="mt-1 break-all text-sm font-bold" title={value}>
        {value}
      </dd>
    </div>
  );
}

function JsonPanel({ title, value }: { title: string; value: Record<string, unknown> | undefined }) {
  return (
    <div>
      <p className="text-sm font-black">{title}</p>
      <div className="mt-2">
        <CodeBlock value={jsonText(value)} />
      </div>
    </div>
  );
}

function CodeBlock({ value }: { value: string }) {
  return (
    <pre className="max-h-80 overflow-auto rounded-lg border border-[var(--app-border)] bg-[#fafafa] p-3 font-mono text-xs font-semibold leading-5 text-[var(--app-text)]">
      <code>{value}</code>
    </pre>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <p className="mt-4 rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa] px-4 py-8 text-center text-sm font-bold text-[var(--app-muted)]">
      {text}
    </p>
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
