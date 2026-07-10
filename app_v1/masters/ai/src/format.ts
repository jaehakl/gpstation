export function parseOptionalInt(value: string, label: string): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed)) {
    throw new Error(`${label} must be an integer`);
  }
  return parsed;
}

export function parseRequiredInt(value: string, label: string): number {
  const parsed = parseOptionalInt(value, label);
  if (parsed === undefined) {
    throw new Error(`${label} is required`);
  }
  return parsed;
}

export function parseOptionalFloat(value: string, label: string): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) {
    throw new Error(`${label} must be a number`);
  }
  return parsed;
}

export function parseRequiredFloat(value: string, label: string): number {
  const parsed = parseOptionalFloat(value, label);
  if (parsed === undefined) {
    throw new Error(`${label} is required`);
  }
  return parsed;
}

export function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function formatClock(value: Date): string {
  return value.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${Math.round(ms)}ms`;
  }
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatDurationSince(startedAt: Date): string {
  return formatDuration(new Date().getTime() - startedAt.getTime());
}
