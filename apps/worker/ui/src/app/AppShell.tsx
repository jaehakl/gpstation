'use client';

import { useCallback, useEffect, useRef, useState, type ReactNode, type TouchEvent } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { DatabaseZap, Home, ImageIcon, PencilLine } from 'lucide-react';
import { useAuthStore, useBootstrapAuth } from '../stores/authStore';
import { useUiStore } from '../stores/uiStore';

const sidebarNavItems = [
  { to: '/context-play', label: 'Context Play', Icon: Home, adminOnly: false },
  { to: '/example-editor', label: 'Example 편집기', Icon: PencilLine, adminOnly: true },
  { to: '/example-explorer', label: 'Example Explorer', Icon: DatabaseZap, adminOnly: true },
  { to: '/image-explorer', label: 'Image Explorer', Icon: ImageIcon, adminOnly: true },
];
const defaultMobileNavVisible = false;

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  useBootstrapAuth();

  const mainRef = useRef<HTMLElement | null>(null);
  const mobileNavButtonRef = useRef<HTMLButtonElement | null>(null);
  const mobileSidebarOverlayRef = useRef<HTMLDivElement | null>(null);
  const lastScrollTopRef = useRef(0);
  const pullStartYRef = useRef<number | null>(null);
  const didShowFromPullRef = useRef(false);
  const pathname = usePathname() ?? '';
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const isMobileSidebarOpen = useUiStore((state) => state.isMobileSidebarOpen);
  const toggleMobileSidebar = useUiStore((state) => state.toggleMobileSidebar);
  const setMobileSidebarOpen = useUiStore((state) => state.setMobileSidebarOpen);
  const shouldShowSidebar = authReady && user !== null;
  const mobileNavResetKey = `${pathname}:${shouldShowSidebar ? 'signed-in' : 'signed-out'}`;
  const [mobileNavState, setMobileNavState] = useState({
    resetKey: mobileNavResetKey,
    isVisible: defaultMobileNavVisible,
  });
  const isMobileNavVisible = mobileNavState.resetKey === mobileNavResetKey
    ? mobileNavState.isVisible
    : defaultMobileNavVisible;

  const closeMobileSidebar = useCallback(() => {
    const activeElement = document.activeElement;
    const overlay = mobileSidebarOverlayRef.current;

    if (activeElement instanceof HTMLElement && overlay?.contains(activeElement)) {
      if (isMobileNavVisible) {
        mobileNavButtonRef.current?.focus();
      } else {
        activeElement.blur();
      }
    }

    setMobileSidebarOpen(false);
  }, [isMobileNavVisible, setMobileSidebarOpen]);

  useEffect(() => {
    closeMobileSidebar();
    lastScrollTopRef.current = mainRef.current?.scrollTop ?? 0;
    pullStartYRef.current = null;
    didShowFromPullRef.current = false;
  }, [closeMobileSidebar, pathname]);

  useEffect(() => {
    if (!shouldShowSidebar) {
      closeMobileSidebar();
      lastScrollTopRef.current = 0;
      pullStartYRef.current = null;
      didShowFromPullRef.current = false;
      return;
    }

    lastScrollTopRef.current = mainRef.current?.scrollTop ?? 0;
    pullStartYRef.current = null;
    didShowFromPullRef.current = false;
  }, [closeMobileSidebar, shouldShowSidebar]);

  useEffect(() => {
    const desktopMediaQuery = window.matchMedia('(min-width: 1024px)');

    if (desktopMediaQuery.matches) {
      closeMobileSidebar();
    }

    const handleDesktopChange = (event: MediaQueryListEvent) => {
      setMobileNavState((state) => {
        if (state.resetKey === mobileNavResetKey && state.isVisible === defaultMobileNavVisible) {
          return state;
        }

        return { resetKey: mobileNavResetKey, isVisible: defaultMobileNavVisible };
      });
      pullStartYRef.current = null;
      didShowFromPullRef.current = false;

      if (event.matches) {
        closeMobileSidebar();
      }
    };

    desktopMediaQuery.addEventListener('change', handleDesktopChange);

    return () => {
      desktopMediaQuery.removeEventListener('change', handleDesktopChange);
    };
  }, [closeMobileSidebar, mobileNavResetKey]);

  const handleMainScroll = () => {
    const main = mainRef.current;

    if (!main) {
      return;
    }

    const scrollTop = main.scrollTop;

    if (
      shouldShowSidebar
      && window.matchMedia('(max-width: 1023px)').matches
      && scrollTop > lastScrollTopRef.current
    ) {
      setMobileNavState((state) => {
        if (state.resetKey === mobileNavResetKey && !state.isVisible) {
          return state;
        }

        return { resetKey: mobileNavResetKey, isVisible: false };
      });
    }

    if (scrollTop > 0) {
      pullStartYRef.current = null;
      didShowFromPullRef.current = false;
    }

    lastScrollTopRef.current = scrollTop;
  };

  const handleMainTouchStart = (event: TouchEvent<HTMLElement>) => {
    const main = mainRef.current;

    if (!shouldShowSidebar || !main || main.scrollTop !== 0) {
      pullStartYRef.current = null;
      didShowFromPullRef.current = false;
      return;
    }

    pullStartYRef.current = event.touches[0]?.clientY ?? null;
    didShowFromPullRef.current = false;
  };

  const handleMainTouchMove = (event: TouchEvent<HTMLElement>) => {
    const main = mainRef.current;
    const startY = pullStartYRef.current;

    if (!shouldShowSidebar || !main || main.scrollTop !== 0 || startY === null || didShowFromPullRef.current) {
      return;
    }

    const currentY = event.touches[0]?.clientY;

    if (currentY !== undefined && currentY - startY >= 40) {
      setMobileNavState((state) => {
        if (state.resetKey === mobileNavResetKey && state.isVisible) {
          return state;
        }

        return { resetKey: mobileNavResetKey, isVisible: true };
      });
      didShowFromPullRef.current = true;
    }
  };

  const handleMainTouchEnd = () => {
    pullStartYRef.current = null;
    didShowFromPullRef.current = false;
  };

  return (
    <div className="h-screen overflow-hidden bg-[var(--app-canvas)] text-[var(--app-text)]">
      <div className="flex h-full min-h-0">
        {shouldShowSidebar ? (
          <div className="hidden h-full min-h-0 w-[280px] shrink-0 lg:flex">
            <Sidebar />
          </div>
        ) : null}

        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          {shouldShowSidebar ? (
            <header
              className={[
                'sticky top-0 z-20 flex shrink-0 items-center gap-3 overflow-hidden bg-[var(--app-header)] px-3 text-white transition-all duration-200 ease-out lg:hidden',
                isMobileNavVisible
                  ? 'h-14 translate-y-0 border-b border-[var(--app-header-border)] opacity-100'
                  : 'pointer-events-none h-0 -translate-y-full border-b-0 opacity-0',
              ].join(' ')}
              inert={isMobileNavVisible ? undefined : true}
            >
              <button
                ref={mobileNavButtonRef}
                type="button"
                aria-controls="mobile-sidebar"
                aria-expanded={isMobileSidebarOpen}
                aria-label="사이드바 열기"
                className="inline-flex h-10 w-10 shrink-0 flex-col items-center justify-center gap-1.5 rounded-full border border-white/20 bg-white text-[#0f0f0f] shadow-sm transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                onClick={toggleMobileSidebar}
              >
                <span className="h-0.5 w-5 rounded-full bg-current" />
                <span className="h-0.5 w-5 rounded-full bg-current" />
                <span className="h-0.5 w-5 rounded-full bg-current" />
              </button>

              <Link
                href="/"
                className="min-w-0 rounded-sm text-sm font-bold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
              >
                Onigiri Neo
              </Link>
            </header>
          ) : null}

          <main
            ref={mainRef}
            className="min-h-0 min-w-0 flex-1 overflow-y-auto bg-[var(--app-canvas)]"
            onScroll={handleMainScroll}
            onTouchStart={handleMainTouchStart}
            onTouchMove={handleMainTouchMove}
            onTouchEnd={handleMainTouchEnd}
            onTouchCancel={handleMainTouchEnd}
          >
            {children}
          </main>
        </div>
      </div>

      {shouldShowSidebar ? (
        <div
          ref={mobileSidebarOverlayRef}
          className={[
            'fixed inset-0 z-40 transition lg:hidden',
            isMobileSidebarOpen ? 'pointer-events-auto' : 'pointer-events-none',
          ].join(' ')}
          inert={isMobileSidebarOpen ? undefined : true}
        >
          <button
            type="button"
            aria-label="사이드바 닫기"
            className={[
              'absolute inset-0 bg-black/50 transition-opacity duration-200',
              isMobileSidebarOpen ? 'opacity-100' : 'opacity-0',
            ].join(' ')}
            onClick={closeMobileSidebar}
          />

          <div
            id="mobile-sidebar"
            className={[
              'relative h-full w-[280px] max-w-[86vw] transform shadow-[var(--app-shadow)] transition-transform duration-200 ease-out',
              isMobileSidebarOpen ? 'translate-x-0' : '-translate-x-full',
            ].join(' ')}
          >
            <Sidebar
              onClose={closeMobileSidebar}
              onNavigate={closeMobileSidebar}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Sidebar({
  onClose,
  onNavigate,
}: {
  onClose?: () => void;
  onNavigate?: () => void;
}) {
  const pathname = usePathname() ?? '';
  const user = useAuthStore((state) => state.user);
  const logoutUser = useAuthStore((state) => state.logoutUser);
  const displayName = user?.display_name?.trim() || user?.email || '사용자';
  const userInitial = displayName.slice(0, 1).toUpperCase();
  const isAdmin = user?.roles.includes('admin') ?? false;
  const visibleNavItems = sidebarNavItems.filter((item) => !item.adminOnly || isAdmin);

  return (
    <aside className="flex h-full w-full flex-col border-r border-[var(--app-border)] bg-[var(--app-sidebar)]">
      <div className="border-b border-[var(--app-border)] px-5 py-5">
        <div className="flex items-center gap-3">
          {onClose ? (
            <button
              type="button"
              aria-label="사이드바 닫기"
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[var(--app-border)] bg-white text-sm font-black transition hover:border-[#bdbdbd] hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
              onClick={onClose}
            >
              <span aria-hidden="true">X</span>
            </button>
          ) : null}
        </div>
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-5 py-5" aria-label="기본 메뉴">
        <p className="mb-2 text-xs font-black uppercase tracking-[0.14em] text-[var(--app-muted)]">
          Menu
        </p>
        <div className="grid gap-2">
          {visibleNavItems.map(({ to, label, Icon }) => {
            const isActive = pathname === to || pathname.startsWith(`${to}/`);

            return (
              <Link
                key={to}
                href={to}
                className={[
                  'flex h-12 items-center gap-3 rounded-lg border px-4 text-sm font-extrabold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                  isActive
                    ? 'border-[#404040] bg-[#2c2c2c] text-white shadow-[0_2px_8px_rgba(0,0,0,0.22)]'
                    : 'border-[#2e2d2d] bg-[#f3f3f3] text-[#0f0f0f] hover:border-[#606060] hover:bg-[#e9e9e9]',
                ].join(' ')}
                onClick={onNavigate}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="truncate">{label}</span>
              </Link>
            );
          })}
        </div>
      </nav>

      <div className="border-t border-[var(--app-border)] p-5">
        <div className="rounded-xl border border-[var(--app-border)] bg-[#fafafa] p-3">
          <div className="space-y-3">
            <div className="flex min-w-0 items-center gap-3">
              <div className="inline-flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-full bg-white text-base font-black shadow-sm">
                {user?.picture_url ? (
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
                {user?.email ? (
                  <p className="truncate text-xs font-semibold text-[var(--app-muted)]" title={user.email}>
                    {user.email}
                  </p>
                ) : null}
              </div>
            </div>
            <button
              type="button"
              className="h-10 w-full rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-extrabold text-[#0f0f0f] transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
              onClick={() => {
                void logoutUser();
              }}
            >
              로그아웃
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}
