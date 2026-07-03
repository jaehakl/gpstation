import type { Metadata, Viewport } from 'next';
import { AppShell } from './AppShell';
import '../styles/index.css';

export const metadata: Metadata = {
  title: 'GPStation Platform',
  description: 'GPStation platform account and operations console',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
