import { Navigate, Route, Routes } from 'react-router-dom';

import { AppShell } from './app/AppShell';
import DashboardPage from './app/page';
import LaunchersPage from './app/launchers/page';
import LoginPage from './app/login/page';
import SlaveSessionsPage from './app/slave-sessions/page';
import UserDetailPage from './app/users/[userId]/page';
import UsersPage from './app/users/page';

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="/users/:userId" element={<UserDetailPage />} />
        <Route path="/launchers" element={<LaunchersPage />} />
        <Route path="/slave-sessions" element={<SlaveSessionsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
