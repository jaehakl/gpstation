import { Eye, RefreshCw, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { dbTables } from '../../api/api';
import type { CrudUserRow } from '../../api/types';
import { useAuthStore } from '../../stores/authStore';
import { AdminGate } from '../AdminGate';
import { displayUserName, errorMessage, formatDate } from '../format';

const pageSize = 100;

export default function UsersPage() {
  return (
    <AdminGate>
      <UsersPageContent />
    </AdminGate>
  );
}

function UsersPageContent() {
  const navigate = useNavigate();
  const currentUser = useAuthStore((state) => state.user);
  const refreshUser = useAuthStore((state) => state.refreshUser);
  const [users, setUsers] = useState<CrudUserRow[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingUserId, setDeletingUserId] = useState<string | null>(null);

  const loadUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await dbTables.users.listRows({ limit: pageSize, sort: ['created_at', 'desc'] });
      setUsers(result.items);
    } catch (loadError) {
      setError(errorMessage(loadError, '사용자 목록을 불러오지 못했습니다.'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadUsers();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadUsers]);

  async function deleteUser(userId: string) {
    if (!window.confirm('이 사용자를 삭제할까요?')) {
      return;
    }
    setDeletingUserId(userId);
    setError(null);
    try {
      await dbTables.users.deleteRows([userId]);
      if (currentUser?.id === userId) {
        await dbTables.auth.logout();
        await refreshUser();
        navigate('/login');
      }
      setUsers((items) => items.filter((item) => item.id !== userId));
    } catch (deleteError) {
      setError(errorMessage(deleteError, '사용자를 삭제하지 못했습니다.'));
    } finally {
      setDeletingUserId(null);
    }
  }

  return (
    <div className="pageWrap sectionStack">
      <div className="pageHeader">
        <div>
          <p className="eyebrow">Admin</p>
          <h1>회원 관리</h1>
        </div>
        <button
          type="button"
          className="button"
          onClick={() => {
            void loadUsers();
          }}
        >
          <RefreshCw size={16} aria-hidden="true" />
          {isLoading ? '새로고침 중' : '새로고침'}
        </button>
      </div>

      {error ? <p className="message danger">{error}</p> : null}

      <section className="tableWrap">
        <div className="scrollTable">
          <table>
            <thead>
              <tr>
                <th>사용자</th>
                <th>권한</th>
                <th>상태</th>
                <th>생성일</th>
                <th style={{ textAlign: 'right' }}>작업</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <EmptyRow colSpan={5} text="사용자 목록을 불러오는 중입니다." />
              ) : users.length === 0 ? (
                <EmptyRow colSpan={5} text="표시할 사용자가 없습니다." />
              ) : (
                users.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{displayUserName(item)}</strong>
                      <div className="mutedText">{item.email ?? '이메일 없음'}</div>
                    </td>
                    <td>
                      <span className="statusPill">{item.role}</span>
                    </td>
                    <td>{item.status}</td>
                    <td>{formatDate(item.created_at)}</td>
                    <td>
                      <div className="rowActions">
                        <Link to={`/users/${item.id}`} className="button smallButton">
                          <Eye size={15} aria-hidden="true" />
                          상세
                        </Link>
                        <button
                          type="button"
                          className="button smallButton dangerButton"
                          disabled={deletingUserId === item.id}
                          onClick={() => {
                            void deleteUser(item.id);
                          }}
                        >
                          <Trash2 size={15} aria-hidden="true" />
                          {deletingUserId === item.id ? '삭제 중' : '삭제'}
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

function EmptyRow({ colSpan, text }: { colSpan: number; text: string }) {
  return (
    <tr>
      <td colSpan={colSpan} className="emptyText">
        {text}
      </td>
    </tr>
  );
}
