import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { AppShell } from './app/AppShell';
import DashboardPage from './app/page';
import LoginPage from './app/login/page';

const ChatPage = lazy(() => import('./app/chat/page'));
const JobsPage = lazy(() => import('./app/jobs/page'));
const LaunchersPage = lazy(() => import('./app/launchers/page'));
const UserDetailPage = lazy(() => import('./app/users/[userId]/page'));
const UsersPage = lazy(() => import('./app/users/page'));

export function App() {
  return (
    <AppShell>
      <Suspense fallback={<div className="centerState">페이지를 불러오는 중입니다.</div>}>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/users" element={<UsersPage />} />
          <Route path="/users/:userId" element={<UserDetailPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/launchers" element={<LaunchersPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </AppShell>
  );
}
