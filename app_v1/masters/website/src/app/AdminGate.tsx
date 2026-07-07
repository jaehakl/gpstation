import { useEffect, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuthStore } from '../stores/authStore';

type AdminGateProps = {
  children: ReactNode;
};

export function AdminGate({ children }: AdminGateProps) {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const isAdmin = user?.role === 'admin' || user?.roles.includes('admin');

  useEffect(() => {
    if (authReady && !isAdmin) {
      navigate('/', { replace: true });
    }
  }, [authReady, isAdmin, navigate]);

  if (!authReady) {
    return <div className="centerState">사용자 정보를 확인 중입니다.</div>;
  }

  if (!isAdmin) {
    return <div className="centerState">대시보드로 이동 중입니다.</div>;
  }

  return children;
}
