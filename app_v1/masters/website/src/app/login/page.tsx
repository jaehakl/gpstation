'use client';

import Link from 'next/link';
import { LogIn, LogOut } from 'lucide-react';

import { useAuthStore } from '../../stores/authStore';
import { displayUserName } from '../format';

export default function LoginPage() {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const startLogin = useAuthStore((state) => state.startLogin);
  const logoutUser = useAuthStore((state) => state.logoutUser);

  return (
    <div className="loginBox panel">
      <p className="eyebrow">GP Station v1</p>
      <h1>로그인</h1>

      {!authReady ? (
        <p className="message warn" style={{ marginTop: 16 }}>사용자 정보를 확인 중입니다.</p>
      ) : user ? (
        <div className="sectionStack" style={{ marginTop: 16 }}>
          <div className="identityBlock" style={{ border: 0, padding: 0 }}>
            <div className="avatar">{displayUserName(user).slice(0, 1).toUpperCase()}</div>
            <div className="identityText">
              <strong>{displayUserName(user)}</strong>
              <span>{user.role} / {user.status}</span>
            </div>
          </div>
          {user.role === 'unauthorized' ? (
            <p className="message warn">
              관리자 승인 전 계정입니다. 승인 전에는 내 계정 조회와 계정 삭제만 사용할 수 있습니다.
            </p>
          ) : null}
          <button
            type="button"
            className="button fullButton"
            onClick={() => {
              void logoutUser();
            }}
          >
            <LogOut size={16} aria-hidden="true" />
            로그아웃
          </button>
          <Link href={`/users/${user.id}`} className="button primaryButton fullButton">
            내 계정으로 이동
          </Link>
        </div>
      ) : (
        <button
          type="button"
          className="button primaryButton fullButton"
          style={{ marginTop: 16 }}
          onClick={startLogin}
        >
          <LogIn size={16} aria-hidden="true" />
          Google로 로그인
        </button>
      )}
    </div>
  );
}
