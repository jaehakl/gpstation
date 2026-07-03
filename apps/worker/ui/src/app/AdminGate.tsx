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
  const isAdmin = user?.roles.includes('admin') ?? false;

  useEffect(() => {
    if (authReady && !isAdmin) {
      router.replace('/context-play');
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
        Context Play로 이동 중입니다.
      </div>
    );
  }

  return children;
}
