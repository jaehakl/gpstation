import { KeyRound, ListChecks, Monitor, RefreshCw, Users } from 'lucide-react';
import type { ReactNode } from 'react';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { dbTables } from '../api/api';
import type { CrudLauncherRow, DashboardSummary, JobData } from '../api/types';
import { useAuthStore } from '../stores/authStore';
import { errorMessage, formatDate } from './format';

export default function DashboardPage() {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [launchers, setLaunchers] = useState<CrudLauncherRow[]>([]);
  const [jobs, setJobs] = useState<JobData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canUseConsole = user?.role === 'admin' || user?.role === 'user';

  const loadDashboard = useCallback(async () => {
    if (!canUseConsole) {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const [nextSummary, nextLaunchers, nextJobs] = await Promise.all([
        dbTables.dashboard.summary(),
        dbTables.launchers.listRows({ limit: 5, sort: ['last_heartbeat_at', 'desc'] }),
        dbTables.jobs.list({ limit: 5 }),
      ]);
      setSummary(nextSummary);
      setLaunchers(nextLaunchers.items);
      setJobs(nextJobs);
    } catch (loadError) {
      setError(errorMessage(loadError, '대시보드를 불러오지 못했습니다.'));
    } finally {
      setIsLoading(false);
    }
  }, [canUseConsole]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadDashboard();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadDashboard]);

  if (!authReady) {
    return <div className="centerState">사용자 정보를 확인 중입니다.</div>;
  }

  if (!user) {
    return (
      <div className="loginBox panel">
        <p className="eyebrow">GP Station v1</p>
        <h1>관리 콘솔</h1>
        <p className="message warn" style={{ marginTop: 16 }}>
          로그인하면 계정, Access Token, Launcher, Job 상태를 관리할 수 있습니다.
        </p>
        <Link to="/login" className="button primaryButton fullButton" style={{ marginTop: 14 }}>
          <KeyRound size={16} aria-hidden="true" />
          로그인으로 이동
        </Link>
      </div>
    );
  }

  if (user.role === 'unauthorized') {
    return (
      <div className="pageWrap">
        <section className="panel">
          <p className="eyebrow">Approval</p>
          <h1>관리자 승인 대기 중</h1>
          <p className="message warn" style={{ marginTop: 16 }}>
            승인 전에는 콘솔에 접근할 수 없습니다. 관리자가 DB에서 role을 admin 또는 user로 변경하면 다시 로그인해 주세요.
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="pageWrap sectionStack">
      <div className="pageHeader">
        <div>
          <p className="eyebrow">Overview</p>
          <h1>대시보드</h1>
        </div>
        <button
          type="button"
          className="button"
          disabled={isLoading}
          onClick={() => {
            void loadDashboard();
          }}
        >
          <RefreshCw size={16} aria-hidden="true" />
          {isLoading ? '새로고침 중' : '새로고침'}
        </button>
      </div>

      {error ? <p className="message danger">{error}</p> : null}

      <section className="gridCards">
        <Metric label="Launchers" value={summary?.launchers ?? 0} icon={<Monitor size={19} aria-hidden="true" />} />
        <Metric label="Jobs" value={jobs.length} icon={<ListChecks size={19} aria-hidden="true" />} />
        <Metric label="Users" value={summary?.users ?? 0} icon={<Users size={19} aria-hidden="true" />} />
        <Metric label="Access Tokens" value={summary?.access_keys ?? 0} icon={<KeyRound size={19} aria-hidden="true" />} />
      </section>

      <div className="twoColumn">
        <section className="panel">
          <div className="toolbar">
            <h2>최근 Launcher</h2>
            <Link to="/launchers" className="button smallButton">
              전체 보기
            </Link>
          </div>
          <div className="tableWrap">
            <div className="scrollTable">
              <table>
                <thead>
                  <tr>
                    <th>이름</th>
                    <th>상태</th>
                    <th>Slave App</th>
                    <th>Heartbeat</th>
                  </tr>
                </thead>
                <tbody>
                  {launchers.map((launcher) => (
                    <tr key={launcher.id}>
                      <td>{launcher.launcher_name}</td>
                      <td>
                        <span className="statusPill">{launcher.status}</span>
                      </td>
                      <td>{launcher.slave_app_ids.join(', ') || '-'}</td>
                      <td>{formatDate(launcher.last_heartbeat_at)}</td>
                    </tr>
                  ))}
                  {launchers.length === 0 ? <EmptyRow colSpan={4} text="표시할 Launcher가 없습니다." /> : null}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="toolbar">
            <h2>최근 Job</h2>
            <Link to="/jobs" className="button smallButton">
              전체 보기
            </Link>
          </div>
          <dl className="detailList">
            {jobs.map((job) => (
              <div className="detailItem" key={job.id}>
                <dt>
                  {job.handler_type} / {job.state}
                </dt>
                <dd>{formatDate(job.created_at)}</dd>
              </div>
            ))}
            {jobs.length === 0 ? <p className="emptyText">표시할 Job이 없습니다.</p> : null}
          </dl>
        </section>
      </div>
    </div>
  );
}

function Metric({ label, value, icon }: { label: string; value: number; icon: ReactNode }) {
  return (
    <div className="metricCard">
      <span>
        {icon} {label}
      </span>
      <strong>{value.toLocaleString('ko-KR')}</strong>
    </div>
  );
}

function EmptyRow({ colSpan, text }: { colSpan: number; text: string }) {
  return (
    <tr>
      <td colSpan={colSpan} className="emptyText">
        {text}
      </td>
    </tr>
  );
}
