'use client';

import { useEffect, type ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '../stores/authStore';

type AdminGateProps = {
  children: ReactNode;
};

export function AdminGate({ children }: AdminGateProps) {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const isAdmin = user?.roles.includes('admin') || user?.role === 'admin';

  useEffect(() => {
    if (authReady && !isAdmin) {
      router.replace('/');
    }
  }, [authReady, isAdmin, router]);

  if (!authReady) {
    return (
      <div className="flex min-h-full items-center justify-center px-4 text-sm font-bold text-[var(--app-muted)]">
        사용자 정보를 확인 중입니다.
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="flex min-h-full items-center justify-center px-4 text-sm font-bold text-[var(--app-muted)]">
        홈으로 이동 중입니다.
      </div>
    );
  }

  return children;
}
