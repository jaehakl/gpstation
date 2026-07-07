import type { UserData } from '../api/types';

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

export function displayUserName(user: UserData) {
  return user.display_name?.trim() || user.username || user.email || user.id;
}

export function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function nullableText(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}
