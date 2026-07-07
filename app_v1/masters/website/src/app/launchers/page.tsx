'use client';

import { RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { api } from '../../api/api';
import type { LauncherSessionView } from '../../api/types';
import { useAuthStore } from '../../stores/authStore';
import { errorMessage, formatDate } from '../format';

export default function LaunchersPage() {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const isAdmin = user?.role === 'admin';
  const canUseConsole = user?.role === 'admin' || user?.role === 'user';
  const [launchers, setLaunchers] = useState<LauncherSessionView[]>([]);
  const [userFilter, setUserFilter] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadLaunchers = useCallback(async () => {
    if (!canUseConsole) {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      setLaunchers(await api.launchers.list(isAdmin ? userFilter.trim() : undefined));
    } catch (loadError) {
      setError(errorMessage(loadError, 'Launcher 목록을 불러오지 못했습니다.'));
    } finally {
      setIsLoading(false);
    }
  }, [canUseConsole, isAdmin, userFilter]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadLaunchers();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadLaunchers]);

  if (!authReady) {
    return <div className="centerState">사용자 정보를 확인 중입니다.</div>;
  }

  if (!canUseConsole) {
    return <div className="centerState">승인된 계정만 Launcher를 볼 수 있습니다.</div>;
  }

  return (
    <div className="pageWrap sectionStack">
      <div className="pageHeader">
        <div>
          <p className="eyebrow">Runtime</p>
          <h1>Launcher 관리</h1>
        </div>
        <button
          type="button"
          className="button"
          disabled={isLoading}
          onClick={() => {
            void loadLaunchers();
          }}
        >
          <RefreshCw size={16} aria-hidden="true" />
          {isLoading ? '새로고침 중' : '새로고침'}
        </button>
      </div>

      {isAdmin ? (
        <section className="panel">
          <div className="filterGrid">
            <label className="field">
              사용자 ID 필터
              <input value={userFilter} onChange={(event) => setUserFilter(event.target.value)} placeholder="비워두면 전체" />
            </label>
            <button
              type="button"
              className="button"
              onClick={() => {
                void loadLaunchers();
              }}
            >
              적용
            </button>
          </div>
        </section>
      ) : null}

      {error ? <p className="message danger">{error}</p> : null}

      <section className="tableWrap">
        <div className="scrollTable">
          <table>
            <thead>
              <tr>
                <th>이름</th>
                <th>사용자</th>
                <th>상태</th>
                <th>Slave 앱</th>
                <th>활성 세션</th>
                <th>IP</th>
                <th>Heartbeat</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <EmptyRow text="Launcher 목록을 불러오는 중입니다." />
              ) : launchers.length === 0 ? (
                <EmptyRow text="표시할 Launcher가 없습니다." />
              ) : (
                launchers.map((launcher) => (
                  <tr key={launcher.id}>
                    <td>
                      <strong>{launcher.launcher_name}</strong>
                      <div className="mono">{launcher.id}</div>
                    </td>
                    <td className="mono">{launcher.user_id}</td>
                    <td><span className="statusPill">{launcher.status}</span></td>
                    <td>{launcher.slave_app_ids.join(', ') || '-'}</td>
                    <td>{launcher.active_session_count}</td>
                    <td>{launcher.ip_address ?? '-'}</td>
                    <td>{formatDate(launcher.last_heartbeat_at)}</td>
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

function EmptyRow({ text }: { text: string }) {
  return (
    <tr>
      <td colSpan={7} className="emptyText">{text}</td>
    </tr>
  );
}
