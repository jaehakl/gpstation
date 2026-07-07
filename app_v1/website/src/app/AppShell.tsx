import { KeyRound, LayoutDashboard, ListChecks, LogIn, LogOut, Monitor, User, Users } from 'lucide-react';
import { type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { useAuthStore, useBootstrapAuth } from '../stores/authStore';

type AppShellProps = {
  children: ReactNode;
};

const navItems = [
  { href: '/', label: '대시보드', icon: LayoutDashboard, roles: ['admin', 'user'] },
  { href: '/jobs', label: 'Job Queue', icon: ListChecks, roles: ['admin', 'user'] },
  { href: '/launchers', label: 'Launcher', icon: Monitor, roles: ['admin', 'user'] },
  { href: '/slave-sessions', label: 'SlaveSession', icon: ListChecks, roles: ['admin', 'user'] },
  { href: '/users', label: '회원 관리', icon: Users, roles: ['admin'] },
];

export function AppShell({ children }: AppShellProps) {
  useBootstrapAuth();

  const { pathname } = useLocation();
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);

  return (
    <div className="appFrame">
      {authReady && user && user.role !== 'unauthorized' ? (
        <aside className="sidebar">
          <Sidebar pathname={pathname} />
        </aside>
      ) : null}
      <div className="appMain">
        <header className="topHeader">
          <Link to="/" className="brand">
            <KeyRound size={18} aria-hidden="true" />
            <span>GP Station v1</span>
          </Link>
          <HeaderAction />
        </header>
        <main className="pageSlot">{children}</main>
      </div>
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

function Sidebar({ pathname }: { pathname: string }) {
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
              <Link key={item.href} to={item.href} className={active ? 'navLink active' : 'navLink'}>
                <Icon size={17} aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        <Link to={accountPath} className={pathname === accountPath ? 'navLink active' : 'navLink'}>
          <User size={17} aria-hidden="true" />
          내 계정
        </Link>
      </nav>

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
    </div>
  );
}
