'use client';

import { RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { dbTables } from '../../api/api';
import type { CrudLauncherRow, CrudUserRow } from '../../api/types';
import { useAuthStore } from '../../stores/authStore';
import { displayUserName, errorMessage, formatDate } from '../format';

export default function LaunchersPage() {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const isAdmin = user?.role === 'admin';
  const canUseConsole = user?.role === 'admin' || user?.role === 'user';
  const [launchers, setLaunchers] = useState<CrudLauncherRow[]>([]);
  const [userLabels, setUserLabels] = useState<Record<string, string>>({});
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
      const trimmedUserFilter = userFilter.trim();
      let matchedUsers: CrudUserRow[] = [];
      let userIds: string[] = [];

      if (isAdmin && trimmedUserFilter) {
        const userResult = await dbTables.users.listRows({ search_text: trimmedUserFilter, limit: 100 });
        matchedUsers = userResult.items;
        userIds = matchedUsers.map((item) => item.id);
        if (userIds.length === 0) {
          setLaunchers([]);
          setUserLabels({});
          return;
        }
      }

      const result = await dbTables.launchers.listRows({
        sort: ['last_heartbeat_at', 'desc'],
        text_filter: userIds.length > 0 ? { user_id: userIds } : {},
      });
      const missingUserIds = Array.from(new Set(result.items.map((item) => item.user_id))).filter(
        (userId) => !matchedUsers.some((item) => item.id === userId),
      );
      const extraUsers = missingUserIds.length > 0
        ? (await dbTables.users.listRows({ selected_ids: missingUserIds, limit: missingUserIds.length })).items
        : [];
      setUserLabels(Object.fromEntries([...matchedUsers, ...extraUsers].map((item) => [item.id, displayUserName(item)])));
      setLaunchers(result.items);
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
              사용자 이름/이메일 필터
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
                <th>Slave App</th>
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
                    </td>
                    <td>{userLabels[launcher.user_id] ?? '사용자'}</td>
                    <td>
                      <span className="statusPill">{launcher.status}</span>
                    </td>
                    <td>{launcher.slave_app_ids.join(', ') || '-'}</td>
                    <td>{launcher.active_session_ids.length}</td>
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
      <td colSpan={7} className="emptyText">
        {text}
      </td>
    </tr>
  );
}
