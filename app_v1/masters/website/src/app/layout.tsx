import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';

import { AppShell } from './AppShell';
import './styles.css';

export const metadata: Metadata = {
  title: 'GP Station v1 Console',
  description: 'GP Station v1 account, token, launcher, and session console',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
