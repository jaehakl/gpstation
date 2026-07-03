'use client';

import Link from 'next/link';
import { LogOut } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';

export default function LoginPage() {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const startLogin = useAuthStore((state) => state.startLogin);
  const logoutUser = useAuthStore((state) => state.logoutUser);
  const displayName = user?.display_name?.trim() || user?.email || '사용자';
  const userInitial = displayName.slice(0, 1).toUpperCase();

  return (
    <div className="flex min-h-full items-center justify-center px-4 py-10">
      <main className="w-full max-w-sm rounded-lg border border-[var(--app-border)] bg-white p-5 shadow-sm">
        <div className="mb-5">
          <p className="text-xs font-black uppercase tracking-[0.14em] text-[var(--app-muted)]">
            Onigiri Neo
          </p>
          <h1 className="mt-1 text-2xl font-black text-[var(--app-text)]">로그인</h1>
        </div>

        {!authReady ? (
          <p className="rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa] px-4 py-8 text-center text-sm font-bold text-[var(--app-muted)]">
            사용자 정보를 확인 중입니다.
          </p>
        ) : user ? (
          <div className="space-y-4">
            <div className="flex min-w-0 items-center gap-3 rounded-lg border border-[var(--app-border)] bg-[#fafafa] p-3">
              <div className="inline-flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-full bg-white text-base font-black shadow-sm">
                {user.picture_url ? (
                  <img
                    src={user.picture_url}
                    alt=""
                    referrerPolicy="no-referrer"
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <span className="text-[#d14343]" aria-hidden="true">
                    {userInitial}
                  </span>
                )}
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-black text-[var(--app-text)]" title={displayName}>
                  {displayName}
                </p>
                {user.email ? (
                  <p className="truncate text-xs font-semibold text-[var(--app-muted)]" title={user.email}>
                    {user.email}
                  </p>
                ) : null}
              </div>
            </div>

            <button
              type="button"
              className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold text-[#0f0f0f] transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
              onClick={() => {
                void logoutUser();
              }}
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              로그아웃
            </button>

            <Link
              href="/context-play"
              className="inline-flex h-11 w-full items-center justify-center rounded-lg border border-[#b02c2c] bg-[var(--app-accent)] px-3 text-sm font-extrabold text-white transition hover:bg-[var(--app-accent-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            >
              Context Play
            </Link>
          </div>
        ) : (
          <button
            type="button"
            className="flex h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#b02c2c] bg-[var(--app-accent)] px-3 text-sm font-extrabold text-white transition hover:bg-[var(--app-accent-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            onClick={startLogin}
          >
            <span
              className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-white text-xs font-black text-[#4285f4]"
              aria-hidden="true"
            >
              G
            </span>
            Google로 로그인
          </button>
        )}
      </main>
    </div>
  );
}
