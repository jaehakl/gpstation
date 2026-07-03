import type { Metadata, Viewport } from 'next';
import { AppShell } from './AppShell';
import '../styles/index.css';

export const metadata: Metadata = {
  title: 'Onigiri Neo',
  description: 'AI 단어장 관리와 Context Play',
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
