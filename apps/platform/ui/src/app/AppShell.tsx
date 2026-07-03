'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, LogIn, LogOut } from 'lucide-react';
import { type ReactNode } from 'react';
import { useAuthStore, useBootstrapAuth } from '../stores/authStore';

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  useBootstrapAuth();

  const pathname = usePathname() ?? '';
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);

  return (
    <div className="min-h-screen bg-[var(--app-canvas)] text-[var(--app-text)]">
      <div className="flex min-h-screen">
        {authReady && user ? (
          <aside className="hidden w-72 shrink-0 border-r border-[var(--app-border)] bg-[var(--app-sidebar)] lg:block">
            <Sidebar pathname={pathname} />
          </aside>
        ) : null}

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--app-border)] bg-white px-4 lg:px-6">
            <Link
              href="/"
              className="text-sm font-black text-[var(--app-text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            >
              GPStation Platform
            </Link>
            <HeaderAction />
          </header>

          <main className="min-h-0 flex-1">{children}</main>
        </div>
      </div>
    </div>
  );
}

function HeaderAction() {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const logoutUser = useAuthStore((state) => state.logoutUser);

  if (!authReady) {
    return <span className="text-xs font-bold text-[var(--app-muted)]">인증 확인 중</span>;
  }

  if (!user) {
    return (
      <Link
        href="/login"
        className="inline-flex h-9 items-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
      >
        <LogIn className="h-4 w-4" aria-hidden="true" />
        로그인
      </Link>
    );
  }

  return (
    <button
      type="button"
      className="inline-flex h-9 items-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
      onClick={() => {
        void logoutUser();
      }}
    >
      <LogOut className="h-4 w-4" aria-hidden="true" />
      로그아웃
    </button>
  );
}

function Sidebar({ pathname }: { pathname: string }) {
  const user = useAuthStore((state) => state.user);
  const logoutUser = useAuthStore((state) => state.logoutUser);
  const displayName = user?.display_name?.trim() || user?.username || user?.email || '사용자';
  const userInitial = displayName.slice(0, 1).toUpperCase();
  const isActive = pathname === '/';

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-[var(--app-border)] p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[var(--app-accent-soft)] text-base font-black text-[var(--app-accent)]">
            {userInitial}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-black" title={displayName}>
              {displayName}
            </p>
            <p className="truncate text-xs font-semibold text-[var(--app-muted)]">
              {user?.role ?? 'user'} / {user?.status ?? 'unknown'}
            </p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-5" aria-label="기본 메뉴">
        <Link
          href="/"
          className={[
            'flex h-12 items-center gap-3 rounded-lg border px-4 text-sm font-extrabold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
            isActive
              ? 'border-[#404040] bg-[#2c2c2c] text-white'
              : 'border-[#2e2d2d] bg-[#f3f3f3] hover:bg-[#e9e9e9]',
          ].join(' ')}
        >
          <LayoutDashboard className="h-4 w-4" aria-hidden="true" />
          홈
        </Link>
      </nav>

      <div className="border-t border-[var(--app-border)] p-5">
        <button
          type="button"
          className="h-10 w-full rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
          onClick={() => {
            void logoutUser();
          }}
        >
          로그아웃
        </button>
      </div>
    </div>
  );
}
