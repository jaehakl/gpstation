'use client';

import { RefreshCw, Square } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { api } from '../../api/api';
import type { SlaveSessionData } from '../../api/types';
import { useAuthStore } from '../../stores/authStore';
import { errorMessage, formatDate } from '../format';

export default function SlaveSessionsPage() {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const isAdmin = user?.role === 'admin';
  const canUseConsole = user?.role === 'admin' || user?.role === 'user';
  const [sessions, setSessions] = useState<SlaveSessionData[]>([]);
  const [userFilter, setUserFilter] = useState('');
  const [closingSessionId, setClosingSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    if (!canUseConsole) {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      setSessions(await api.slaveSessions.list(isAdmin ? userFilter.trim() : undefined));
    } catch (loadError) {
      setError(errorMessage(loadError, 'SlaveSession 목록을 불러오지 못했습니다.'));
    } finally {
      setIsLoading(false);
    }
  }, [canUseConsole, isAdmin, userFilter]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadSessions();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadSessions]);

  async function closeSession(sessionId: string) {
    if (!window.confirm('이 SlaveSession을 종료할까요?')) {
      return;
    }
    setClosingSessionId(sessionId);
    setError(null);
    setMessage(null);
    try {
      await api.slaveSessions.close(sessionId);
      setMessage('SlaveSession을 종료했습니다.');
      await loadSessions();
    } catch (closeError) {
      setError(errorMessage(closeError, 'SlaveSession을 종료하지 못했습니다.'));
    } finally {
      setClosingSessionId(null);
    }
  }

  if (!authReady) {
    return <div className="centerState">사용자 정보를 확인 중입니다.</div>;
  }

  if (!canUseConsole) {
    return <div className="centerState">승인된 계정만 SlaveSession을 볼 수 있습니다.</div>;
  }

  return (
    <div className="pageWrap sectionStack">
      <div className="pageHeader">
        <div>
          <p className="eyebrow">Runtime</p>
          <h1>SlaveSession 관리</h1>
        </div>
        <button
          type="button"
          className="button"
          disabled={isLoading}
          onClick={() => {
            void loadSessions();
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
                void loadSessions();
              }}
            >
              적용
            </button>
          </div>
        </section>
      ) : null}

      {error ? <p className="message danger">{error}</p> : null}
      {message ? <p className="message success">{message}</p> : null}

      <section className="tableWrap">
        <div className="scrollTable">
          <table>
            <thead>
              <tr>
                <th>세션</th>
                <th>사용자</th>
                <th>Launcher</th>
                <th>Slave 앱</th>
                <th>상태</th>
                <th>만료</th>
                <th style={{ textAlign: 'right' }}>작업</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <EmptyRow text="SlaveSession 목록을 불러오는 중입니다." />
              ) : sessions.length === 0 ? (
                <EmptyRow text="표시할 SlaveSession이 없습니다." />
              ) : (
                sessions.map((session) => (
                  <tr key={session.id}>
                    <td>
                      <strong className="mono">{session.id}</strong>
                      <div className="mutedText">{formatDate(session.created_at)}</div>
                    </td>
                    <td className="mono">{session.user_id}</td>
                    <td className="mono">{session.launcher_id ?? '-'}</td>
                    <td>{session.slave_app_id}</td>
                    <td><span className="statusPill">{session.status}</span></td>
                    <td>{formatDate(session.expires_at)}</td>
                    <td>
                      <div className="rowActions">
                        <button
                          type="button"
                          className="button smallButton dangerButton"
                          disabled={!['starting', 'ready'].includes(session.status) || closingSessionId === session.id}
                          onClick={() => {
                            void closeSession(session.id);
                          }}
                        >
                          <Square size={15} aria-hidden="true" />
                          {closingSessionId === session.id ? '종료 중' : '종료'}
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

function EmptyRow({ text }: { text: string }) {
  return (
    <tr>
      <td colSpan={7} className="emptyText">{text}</td>
    </tr>
  );
}
