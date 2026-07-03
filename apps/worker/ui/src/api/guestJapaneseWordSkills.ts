import type { AnalyzeJapaneseTextSkills } from './types';

const STORAGE_KEY = 'neo_guest_jp_word_skills_v1';

type StoredSkill = {
  reading?: number | null;
  updated_at?: string | null;
};

type SkillStore = Record<string, StoredSkill | number | null | undefined>;

function clampReading(value: unknown): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(parsed)));
}

function readStore(): SkillStore {
  if (typeof window === 'undefined') {
    return {};
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? parsed as SkillStore
      : {};
  } catch {
    return {};
  }
}

function writeStore(store: SkillStore) {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch {
    // Ignore unavailable storage or quota failures.
  }
}

export function getGuestJapaneseTextSkills(): AnalyzeJapaneseTextSkills {
  const store = readStore();
  return Object.entries(store).reduce<Record<string, { reading: number; updated_at: string | null }>>(
    (skills, [wordId, value]) => {
      if (!Number.isInteger(Number(wordId))) {
        return skills;
      }

      if (value && typeof value === 'object') {
        skills[wordId] = {
          reading: clampReading(value.reading),
          updated_at: typeof value.updated_at === 'string' ? value.updated_at : null,
        };
        return skills;
      }

      skills[wordId] = {
        reading: clampReading(value),
        updated_at: null,
      };
      return skills;
    },
    {},
  );
}

export function saveGuestJapaneseWordSkill(wordId: number, reading: number) {
  const updated_at = new Date().toISOString();
  const skill = {
    reading: clampReading(reading),
    updated_at,
  };
  const store = readStore();
  store[String(wordId)] = skill;
  writeStore(store);
  return skill;
}
