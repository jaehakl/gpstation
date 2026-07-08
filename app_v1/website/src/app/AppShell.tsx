import { KeyRound, LayoutDashboard, ListChecks, LogIn, LogOut, Menu, MessageCircle, Monitor, User, Users, X } from 'lucide-react';
import { type ReactNode, useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { useAuthStore, useBootstrapAuth } from '../stores/authStore';

type AppShellProps = {
  children: ReactNode;
};

const navItems = [
  { href: '/', label: '대시보드', icon: LayoutDashboard, roles: ['admin', 'user'] },
  { href: '/chat', label: 'AI Chat', icon: MessageCircle, roles: ['admin', 'user'] },
  { href: '/jobs', label: 'Job Queue', icon: ListChecks, roles: ['admin', 'user'] },
  { href: '/launchers', label: 'Launcher', icon: Monitor, roles: ['admin', 'user'] },
  { href: '/users', label: '회원 관리', icon: Users, roles: ['admin'] },
];

export function AppShell({ children }: AppShellProps) {
  useBootstrapAuth();

  const { pathname } = useLocation();
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const [mobileMenuPath, setMobileMenuPath] = useState<string | null>(null);
  const authenticated = authReady && user && user.role !== 'unauthorized';
  const isChatPage = pathname === '/chat' || pathname.startsWith('/chat/');
  const mobileMenuOpen = Boolean(authenticated && mobileMenuPath === pathname);

  useEffect(() => {
    if (mobileMenuPath === null || (authenticated && mobileMenuPath === pathname)) {
      return;
    }
    const timeoutId = window.setTimeout(() => setMobileMenuPath(null), 0);
    return () => window.clearTimeout(timeoutId);
  }, [authenticated, mobileMenuPath, pathname]);

  useEffect(() => {
    if (!mobileMenuOpen) {
      return;
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setMobileMenuPath(null);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [mobileMenuOpen]);

  return (
    <div className="appFrame">
      {authenticated ? (
        <aside className="sidebar desktopSidebar">
          <Sidebar pathname={pathname} />
        </aside>
      ) : null}
      <div className="appMain">
        <header className="topHeader">
          <div className="brandGroup">
            {authenticated ? (
              <button
                type="button"
                className="button iconButton mobileMenuButton"
                aria-controls="mobile-sidebar"
                aria-expanded={mobileMenuOpen}
                onClick={() => setMobileMenuPath(pathname)}
              >
                <Menu size={18} aria-hidden="true" />
                <span className="visuallyHidden">Menu</span>
              </button>
            ) : null}
            <Link to="/" className="brand">
              <KeyRound size={18} aria-hidden="true" />
              <span>GP Station v1</span>
            </Link>
          </div>
          <HeaderAction />
        </header>
        <main className={isChatPage ? 'pageSlot chatPageSlot' : 'pageSlot'}>{children}</main>
      </div>
      {authenticated && mobileMenuOpen ? (
        <div className="mobileSidebarLayer" role="presentation" onMouseDown={() => setMobileMenuPath(null)}>
          <aside
            id="mobile-sidebar"
            className="mobileSidebar"
            aria-label="Mobile navigation"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="mobileSidebarHeader">
              <strong>Menu</strong>
              <button type="button" className="button iconButton" onClick={() => setMobileMenuPath(null)}>
                <X size={18} aria-hidden="true" />
                <span className="visuallyHidden">Close menu</span>
              </button>
            </div>
            <Sidebar pathname={pathname} onNavigate={() => setMobileMenuPath(null)} />
          </aside>
        </div>
      ) : null}
    </div>
  );
}

function HeaderAction() {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const logoutUser = useAuthStore((state) => state.logoutUser);

  if (!authReady) {
    return <span className="mutedText">인증 확인 중</span>;
  }

  if (!user || user.role === 'unauthorized') {
    return (
      <Link to="/login" className="button smallButton">
        <LogIn size={16} aria-hidden="true" />
        로그인
      </Link>
    );
  }

  return (
    <button
      type="button"
      className="button smallButton"
      onClick={() => {
        void logoutUser();
      }}
    >
      <LogOut size={16} aria-hidden="true" />
      로그아웃
    </button>
  );
}

function Sidebar({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  const user = useAuthStore((state) => state.user);
  const logoutUser = useAuthStore((state) => state.logoutUser);
  const displayName = user?.display_name?.trim() || user?.username || user?.email || '사용자';
  const role = user?.role ?? 'unauthorized';
  const accountPath = user ? `/users/${user.id}` : '/login';

  return (
    <div className="sidebarInner">
      <div className="identityBlock">
        <div className="avatar">{displayName.slice(0, 1).toUpperCase()}</div>
        <div className="identityText">
          <strong title={displayName}>{displayName}</strong>
          <span>{role} / {user?.status ?? 'unknown'}</span>
        </div>
      </div>

      <nav className="sideNav" aria-label="기본 메뉴">
        {navItems
          .filter((item) => item.roles.includes(role))
          .map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || (item.href !== '/' && pathname.startsWith(`${item.href}/`));
            return (
              <Link key={item.href} to={item.href} className={active ? 'navLink active' : 'navLink'} onClick={onNavigate}>
                <Icon size={17} aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        <Link to={accountPath} className={pathname === accountPath ? 'navLink active' : 'navLink'} onClick={onNavigate}>
          <User size={17} aria-hidden="true" />
          내 계정
        </Link>
      </nav>

      <button
        type="button"
        className="button fullButton"
        onClick={() => {
          onNavigate?.();
          void logoutUser();
        }}
      >
        <LogOut size={16} aria-hidden="true" />
        로그아웃
      </button>
    </div>
  );
}
