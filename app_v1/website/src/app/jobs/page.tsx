import { RefreshCw, Square } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { dbTables } from '../../api/api';
import type { CrudLauncherRow, CrudUserRow, JobData } from '../../api/types';
import { useAuthStore } from '../../stores/authStore';
import { displayLauncherName, displayUserName, errorMessage, formatDate } from '../format';

const ACTIVE_JOB_STATES = ['queued', 'assigned', 'answer_ready', 'running'];

export default function JobsPage() {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const isAdmin = user?.role === 'admin';
  const canUseConsole = user?.role === 'admin' || user?.role === 'user';
  const [jobs, setJobs] = useState<JobData[]>([]);
  const [userLabels, setUserLabels] = useState<Record<string, string>>({});
  const [launcherLabels, setLauncherLabels] = useState<Record<string, string>>({});
  const [userFilter, setUserFilter] = useState('');
  const [activeOnly, setActiveOnly] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [killingJobId, setKillingJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadJobs = useCallback(async () => {
    if (!canUseConsole) {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const trimmedUserFilter = userFilter.trim();
      let matchedUsers: CrudUserRow[] = [];
      let allowedUserIds: string[] | null = null;

      if (isAdmin && trimmedUserFilter) {
        const userResult = await dbTables.users.listRows({ search_text: trimmedUserFilter, limit: 100 });
        matchedUsers = userResult.items;
        allowedUserIds = matchedUsers.map((item) => item.id);
        if (allowedUserIds.length === 0) {
          setJobs([]);
          setUserLabels({});
          setLauncherLabels({});
          return;
        }
      }

      const result = await dbTables.jobs.list({ activeOnly, limit: 200 });
      const visibleJobs = allowedUserIds ? result.filter((job) => allowedUserIds.includes(job.user_id)) : result;
      const missingUserIds = Array.from(new Set(visibleJobs.map((job) => job.user_id))).filter(
        (userId) => !matchedUsers.some((item) => item.id === userId),
      );
      const launcherIds = Array.from(new Set(visibleJobs.map((job) => job.launcher_id).filter((item): item is string => Boolean(item))));
      const [extraUsers, launchers] = await Promise.all([
        missingUserIds.length > 0 ? dbTables.users.listRows({ selected_ids: missingUserIds, limit: missingUserIds.length }) : Promise.resolve({ items: [] as CrudUserRow[], total: 0 }),
        launcherIds.length > 0 ? dbTables.launchers.listRows({ selected_ids: launcherIds, limit: launcherIds.length }) : Promise.resolve({ items: [] as CrudLauncherRow[], total: 0 }),
      ]);
      setUserLabels(Object.fromEntries([...matchedUsers, ...extraUsers.items].map((item) => [item.id, displayUserName(item)])));
      setLauncherLabels(Object.fromEntries(launchers.items.map((item) => [item.id, displayLauncherName(item)])));
      setJobs(visibleJobs);
    } catch (loadError) {
      setError(errorMessage(loadError, 'Job 목록을 불러오지 못했습니다.'));
    } finally {
      setIsLoading(false);
    }
  }, [activeOnly, canUseConsole, isAdmin, userFilter]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadJobs();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadJobs]);

  async function killJob(jobId: string) {
    if (!window.confirm('이 Job을 kill할까요? 실행 중이면 현재 worker에 취소 요청이 전달됩니다.')) {
      return;
    }
    setKillingJobId(jobId);
    setError(null);
    setMessage(null);
    try {
      await dbTables.jobs.kill(jobId);
      setMessage('Job kill을 요청했습니다.');
      await loadJobs();
    } catch (killError) {
      setError(errorMessage(killError, 'Job을 kill하지 못했습니다.'));
    } finally {
      setKillingJobId(null);
    }
  }

  if (!authReady) {
    return <div className="centerState">사용자 정보를 확인 중입니다.</div>;
  }

  if (!canUseConsole) {
    return <div className="centerState">승인된 계정만 Job을 볼 수 있습니다.</div>;
  }

  return (
    <div className="pageWrap sectionStack">
      <div className="pageHeader">
        <div>
          <p className="eyebrow">Queue</p>
          <h1>Job 관리</h1>
        </div>
        <button
          type="button"
          className="button"
          disabled={isLoading}
          onClick={() => {
            void loadJobs();
          }}
        >
          <RefreshCw size={16} aria-hidden="true" />
          {isLoading ? '새로고침 중' : '새로고침'}
        </button>
      </div>

      <section className="panel">
        <div className="toolbar">
          {isAdmin ? (
            <label className="field">
              사용자 이름/이메일 필터
              <input value={userFilter} onChange={(event) => setUserFilter(event.target.value)} placeholder="비워두면 전체" />
            </label>
          ) : (
            <span className="mutedText">내 Job</span>
          )}
          <div className="checkRow">
            <label className="checkField">
              <input type="checkbox" checked={activeOnly} onChange={(event) => setActiveOnly(event.target.checked)} />
              활성만
            </label>
            <button
              type="button"
              className="button"
              onClick={() => {
                void loadJobs();
              }}
            >
              적용
            </button>
          </div>
        </div>
      </section>

      {error ? <p className="message danger">{error}</p> : null}
      {message ? <p className="message success">{message}</p> : null}

      <section className="tableWrap">
        <div className="scrollTable">
          <table>
            <thead>
              <tr>
                <th>Job</th>
                <th>사용자</th>
                <th>Handler</th>
                <th>상태</th>
                <th>Launcher</th>
                <th>대기</th>
                <th>실행</th>
                <th>시도</th>
                <th>오류</th>
                <th style={{ textAlign: 'right' }}>작업</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <EmptyRow text="Job 목록을 불러오는 중입니다." />
              ) : jobs.length === 0 ? (
                <EmptyRow text="표시할 Job이 없습니다." />
              ) : (
                jobs.map((job) => (
                  <tr key={job.id}>
                    <td>
                      <strong className="mono">{job.id}</strong>
                      <div className="mutedText">{formatDate(job.created_at)}</div>
                    </td>
                    <td>{userLabels[job.user_id] ?? '사용자'}</td>
                    <td>
                      <strong>{job.handler_type}</strong>
                      <div className="mutedText">{job.slave_app_id}</div>
                    </td>
                    <td>
                      <span className="statusPill">{job.state}</span>
                    </td>
                    <td>{job.launcher_id ? launcherLabels[job.launcher_id] ?? 'Launcher' : '-'}</td>
                    <td>{formatElapsed(job.created_at, job.assigned_at ?? job.finished_at)}</td>
                    <td>{formatElapsed(job.started_at, job.finished_at)}</td>
                    <td>{job.attempt_count}</td>
                    <td className="mono">{job.last_error ?? '-'}</td>
                    <td>
                      <div className="rowActions">
                        <button
                          type="button"
                          className="button smallButton dangerButton"
                          disabled={!ACTIVE_JOB_STATES.includes(job.state) || killingJobId === job.id}
                          onClick={() => {
                            void killJob(job.id);
                          }}
                        >
                          <Square size={15} aria-hidden="true" />
                          {killingJobId === job.id ? 'Kill 중' : 'Kill'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function formatElapsed(start: string | null | undefined, end: string | null | undefined) {
  if (!start) {
    return '-';
  }
  const startMs = new Date(start).getTime();
  const endMs = end ? new Date(end).getTime() : Date.now();
  if (Number.isNaN(startMs) || Number.isNaN(endMs) || endMs < startMs) {
    return '-';
  }
  const seconds = Math.round((endMs - startMs) / 1000);
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
}

function EmptyRow({ text }: { text: string }) {
  return (
    <tr>
      <td colSpan={10} className="emptyText">
        {text}
      </td>
    </tr>
  );
}
