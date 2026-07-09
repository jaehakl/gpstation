import { LogIn, LogOut } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';

import { useAuthStore } from '../../stores/authStore';
import { displayUserName } from '../format';

export default function LoginPage() {
  return <LoginContent />;
}

function LoginContent() {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const startLogin = useAuthStore((state) => state.startLogin);
  const logoutUser = useAuthStore((state) => state.logoutUser);
  const [searchParams] = useSearchParams();
  const approvalRequired = searchParams.get('approval_required') === '1';

  return (
    <div className="loginBox panel">
      <p className="eyebrow">GP Station v1</p>
      <h1>로그인</h1>

      {!authReady ? (
        <p className="message warn" style={{ marginTop: 16 }}>사용자 정보를 확인 중입니다.</p>
      ) : user && user.role !== 'unauthorized' ? (
        <div className="sectionStack" style={{ marginTop: 16 }}>
          <div className="identityBlock" style={{ border: 0, padding: 0 }}>
            <div className="avatar">{displayUserName(user).slice(0, 1).toUpperCase()}</div>
            <div className="identityText">
              <strong>{displayUserName(user)}</strong>
              <span>{user.role} / {user.status}</span>
            </div>
          </div>
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
          <Link to={`/users/${user.id}`} className="button primaryButton fullButton">
            내 계정으로 이동
          </Link>
        </div>
      ) : (
        <>
          {approvalRequired ? (
            <p className="message warn" style={{ marginTop: 16 }}>
              관리자 승인 전에는 콘솔에 접근할 수 없습니다. 이용 신청은{' '}
              <a href="mailto:jaehak@qutat.com">jaehak@qutat.com</a> 으로 문의해 주세요.
            </p>
          ) : null}
          <button
            type="button"
            className="button primaryButton fullButton"
            style={{ marginTop: 16 }}
            onClick={startLogin}
          >
            <LogIn size={16} aria-hidden="true" />
            Google로 로그인
          </button>
          <p className="message warn" style={{ marginTop: 12 }}>
            로그인 또는 승인이 어려운 경우{' '}
            <a href="https://github.com/jaehakl/gpstation" target="_blank" rel="noreferrer">
              jaehakl/gpstation
            </a>{' '}
            소스코드를 활용해 직접 GP Station 서버를 구축할 수 있습니다.
          </p>
        </>
      )}
    </div>
  );
}
