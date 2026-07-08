export function formatDate(value: string | null | undefined) {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('ko-KR');
}

export function displayUserName(user: { display_name?: string | null; username?: string | null; email?: string | null }) {
  return user.display_name?.trim() || user.username?.trim() || user.email?.trim() || '사용자';
}

export function displayAccessKeyName(accessKey: { name?: string | null }) {
  return accessKey.name?.trim() || 'Access Token';
}

export function displayLauncherName(launcher: { ip_address?: string | null; launcher_name?: string | null }) {
  return launcher.ip_address?.trim() || launcher.launcher_name?.trim() || 'Launcher';
}

export function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function nullableText(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}
