import { RefreshCw, RotateCcw, Square, Wrench } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { dbTables } from '../../api/api';
import type { CrudLauncherRow, CrudUserRow, LauncherRuntimeData } from '../../api/types';
import { useAuthStore } from '../../stores/authStore';
import { displayUserName, errorMessage, formatDate } from '../format';

const ACTIVE_LAUNCHER_STATUSES = ['ready', 'busy'];

export default function LaunchersPage() {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const isAdmin = user?.role === 'admin';
  const canUseConsole = user?.role === 'admin' || user?.role === 'user';
  const [launchers, setLaunchers] = useState<CrudLauncherRow[]>([]);
  const [launcherRuntime, setLauncherRuntime] = useState<Record<string, LauncherRuntimeData>>({});
  const [userLabels, setUserLabels] = useState<Record<string, string>>({});
  const [userFilter, setUserFilter] = useState('');
  const [activeOnly, setActiveOnly] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [isReconciling, setIsReconciling] = useState(false);
  const [actionLauncherId, setActionLauncherId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

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

      const textFilter: Record<string, string[]> = {};
      if (userIds.length > 0) {
        textFilter.user_id = userIds;
      }
      if (activeOnly) {
        textFilter.status = ACTIVE_LAUNCHER_STATUSES;
      }
      const result = await dbTables.launchers.listRows({
        sort: ['last_heartbeat_at', 'desc'],
        text_filter: textFilter,
      });
      const items = activeOnly ? result.items.filter((item) => !item.disconnected_at) : result.items;
      const missingUserIds = Array.from(new Set(items.map((item) => item.user_id))).filter(
        (userId) => !matchedUsers.some((item) => item.id === userId),
      );
      const [extraUsers, runtimeRows] = await Promise.all([
        missingUserIds.length > 0
          ? dbTables.users.listRows({ selected_ids: missingUserIds, limit: missingUserIds.length })
          : Promise.resolve({ items: [] as CrudUserRow[], total: 0 }),
        dbTables.launchers.runtime(),
      ]);
      setUserLabels(Object.fromEntries([...matchedUsers, ...extraUsers.items].map((item) => [item.id, displayUserName(item)])));
      setLauncherRuntime(Object.fromEntries(runtimeRows.map((item) => [item.launcher_id, item])));
      setLaunchers(items);
    } catch (loadError) {
      setError(errorMessage(loadError, 'Launcher 목록을 불러오지 못했습니다.'));
    } finally {
      setIsLoading(false);
    }
  }, [activeOnly, canUseConsole, isAdmin, userFilter]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadLaunchers();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadLaunchers]);

  async function reconcileDisconnectedLaunchers() {
    setIsReconciling(true);
    setError(null);
    setMessage(null);
    try {
      const result = await dbTables.launchers.reconcileDisconnected();
      setMessage(`Launcher ${result.launchers}개, SlaveSession ${result.slave_sessions}개를 보정했습니다.`);
      await loadLaunchers();
    } catch (reconcileError) {
      setError(errorMessage(reconcileError, 'Launcher 상태를 보정하지 못했습니다.'));
    } finally {
      setIsReconciling(false);
    }
  }

  async function cancelCurrentJob(launcherId: string) {
    if (!window.confirm('이 Launcher의 현재 Job을 취소할까요?')) {
      return;
    }
    setActionLauncherId(launcherId);
    setError(null);
    setMessage(null);
    try {
      await dbTables.launchers.cancelCurrentJob(launcherId);
      setMessage('현재 Job 취소를 요청했습니다.');
      await loadLaunchers();
    } catch (cancelError) {
      setError(errorMessage(cancelError, '현재 Job을 취소하지 못했습니다.'));
    } finally {
      setActionLauncherId(null);
    }
  }

  async function resetWorker(launcherId: string) {
    if (!window.confirm('이 Launcher의 worker subprocess를 재시작할까요? 현재 Job이 있으면 취소됩니다.')) {
      return;
    }
    setActionLauncherId(launcherId);
    setError(null);
    setMessage(null);
    try {
      await dbTables.launchers.resetWorker(launcherId);
      setMessage('Worker reset을 요청했습니다.');
      await loadLaunchers();
    } catch (resetError) {
      setError(errorMessage(resetError, 'Worker reset을 요청하지 못했습니다.'));
    } finally {
      setActionLauncherId(null);
    }
  }

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
        <div className="rowActions">
          <button
            type="button"
            className="button"
            disabled={isReconciling}
            onClick={() => {
              void reconcileDisconnectedLaunchers();
            }}
          >
            <Wrench size={16} aria-hidden="true" />
            {isReconciling ? '보정 중' : '상태 보정'}
          </button>
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
      </div>

      <section className="panel">
        <div className="toolbar">
          {isAdmin ? (
            <label className="field">
              사용자 이름/이메일 필터
              <input value={userFilter} onChange={(event) => setUserFilter(event.target.value)} placeholder="비워두면 전체" />
            </label>
          ) : (
            <span className="mutedText">내 Launcher</span>
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
                void loadLaunchers();
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
                <th>이름</th>
                <th>사용자</th>
                <th>상태</th>
                <th>Slave App</th>
                <th>활성 세션</th>
                <th>Worker</th>
                <th>현재 Job</th>
                <th>IP</th>
                <th>Heartbeat</th>
                <th style={{ textAlign: 'right' }}>작업</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <EmptyRow text="Launcher 목록을 불러오는 중입니다." />
              ) : launchers.length === 0 ? (
                <EmptyRow text="표시할 Launcher가 없습니다." />
              ) : (
                launchers.map((launcher) => {
                  const runtime = launcherRuntime[launcher.id];
                  return (
                    <tr key={launcher.id}>
                      <td>
                        <strong>{launcher.launcher_name}</strong>
                      </td>
                      <td>{userLabels[launcher.user_id] ?? '사용자'}</td>
                      <td>
                        <span className="statusPill">{launcher.status}</span>
                      </td>
                      <td>{launcher.slave_app_ids.join(', ') || '-'}</td>
                      <td>{runtime?.active_session_ids.length ?? launcher.active_session_ids.length}</td>
                      <td>
                        <span className="statusPill">{runtime?.worker_status ?? 'offline'}</span>
                        <div className="mutedText">{runtime?.loaded_slave_app_id ?? '-'}</div>
                      </td>
                      <td className="mono">{runtime?.current_job_id ?? '-'}</td>
                      <td>{launcher.ip_address ?? '-'}</td>
                      <td>{formatDate(launcher.last_heartbeat_at)}</td>
                      <td>
                        <div className="rowActions">
                          <button
                            type="button"
                            className="button smallButton dangerButton"
                            disabled={!runtime?.current_job_id || actionLauncherId === launcher.id}
                            onClick={() => {
                              void cancelCurrentJob(launcher.id);
                            }}
                          >
                            <Square size={15} aria-hidden="true" />
                            Job 취소
                          </button>
                          <button
                            type="button"
                            className="button smallButton"
                            disabled={!runtime || actionLauncherId === launcher.id}
                            onClick={() => {
                              void resetWorker(launcher.id);
                            }}
                          >
                            <RotateCcw size={15} aria-hidden="true" />
                            Reset
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
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
      <td colSpan={10} className="emptyText">
        {text}
      </td>
    </tr>
  );
}
