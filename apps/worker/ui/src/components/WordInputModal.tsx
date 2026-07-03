import { useState } from 'react';
import { createPortal } from 'react-dom';
import { Save, Sparkles, Trash2, X } from 'lucide-react';

export type WordInputModalValue = {
  id?: string;
  wordId?: number | null;
  lemmaId?: number | null;
  lemma?: string;
  surface?: string;
  jpPron?: string;
  krMean: string;
  reading?: number;
  userWordSkill?: {
    id?: number | null;
    reading: number;
    listening?: number;
    speaking?: number;
  } | null;
};

type WordInputModalProps = {
  isOpen: boolean;
  word: WordInputModalValue | null;
  isAdmin: boolean;
  canSaveSkill: boolean;
  onClose: () => void;
  onSubmit: (word: WordInputModalValue) => Promise<void> | void;
  onDelete?: (wordId: number) => Promise<void> | void;
  onFetchMeaning?: () => Promise<string>;
};

const emptyWord: WordInputModalValue = {
  wordId: null,
  lemmaId: null,
  krMean: '',
};

function clampReading(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

export function WordInputModal({
  isOpen,
  word,
  isAdmin,
  canSaveSkill,
  onClose,
  onSubmit,
  onDelete,
  onFetchMeaning,
}: WordInputModalProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <WordInputModalBody
      key={word?.id ?? 'empty-word'}
      word={word}
      isAdmin={isAdmin}
      canSaveSkill={canSaveSkill}
      onClose={onClose}
      onSubmit={onSubmit}
      onDelete={onDelete}
      onFetchMeaning={onFetchMeaning}
    />
  );
}

function WordInputModalBody({
  word,
  isAdmin,
  canSaveSkill,
  onClose,
  onSubmit,
  onDelete,
  onFetchMeaning,
}: Omit<WordInputModalProps, 'isOpen'>) {
  const initialWord = word ? { ...emptyWord, ...word } : emptyWord;
  const [form, setForm] = useState<WordInputModalValue>(initialWord);
  const [reading, setReading] = useState(
    clampReading(initialWord.reading ?? initialWord.userWordSkill?.reading ?? 0),
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFetchingMeaning, setIsFetchingMeaning] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const hasPersistableWord = form.wordId != null || (isAdmin && form.lemmaId != null);
  const hasRequiredLemma = !isAdmin || Boolean(form.lemma?.trim());
  const isBusy = isSubmitting || isFetchingMeaning;
  const canSubmit = Boolean(form.id) && hasPersistableWord && hasRequiredLemma && !isBusy;
  const canEditLemma = isAdmin && hasPersistableWord && !isBusy;
  const canEditMeaning =
    isAdmin && hasPersistableWord && !isBusy;
  const canEditReading = canSaveSkill && hasPersistableWord && !isBusy;
  const showDeleteButton = isAdmin && form.wordId != null && Boolean(onDelete);

  const updateReading = (value: number) => {
    setReading(clampReading(value));
  };

  const handleSubmit = async () => {
    if (!canSubmit) {
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);
    try {
      await onSubmit({
        ...form,
        reading,
      });
      onClose();
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : '단어 정보를 저장하지 못했습니다.',
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (form.wordId == null || !onDelete) {
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);
    try {
      await onDelete(form.wordId);
      onClose();
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : '단어를 삭제하지 못했습니다.',
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFetchMeaning = async (mode: 'replace' | 'append') => {
    if (!onFetchMeaning || !canEditMeaning) {
      return;
    }

    setIsFetchingMeaning(true);
    setSubmitError(null);
    try {
      const nextMeaning = await onFetchMeaning();
      const trimmedMeaning = nextMeaning.trim();
      if (!trimmedMeaning) {
        throw new Error('한국어 뜻을 가져오지 못했습니다.');
      }
      setForm((currentForm) => ({
        ...currentForm,
        krMean:
          mode === 'replace'
            ? trimmedMeaning
            : currentForm.krMean.trim()
              ? `${currentForm.krMean.trim()}, ${trimmedMeaning}`
              : trimmedMeaning,
      }));
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : '한국어 뜻을 가져오지 못했습니다.',
      );
    } finally {
      setIsFetchingMeaning(false);
    }
  };

  const body = (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 px-4 py-6"
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="word-input-modal-title"
        className="flex max-h-full w-full max-w-xl flex-col overflow-hidden rounded-lg border border-[#0f0f0f] bg-white shadow-[var(--app-shadow)]"
      >
        <header className="flex min-h-14 items-center gap-3 border-b border-[var(--app-border)] bg-[#0f0f0f] px-4 text-white">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-black uppercase text-white/55">Word</p>
            <h2 id="word-input-modal-title" className="truncate text-lg font-black">
              {form.surface || form.lemma || '단어 입력'}
            </h2>
          </div>
          <button
            type="button"
            aria-label="단어 입력 모달 닫기"
            title="닫기"
            disabled={isBusy}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/20 bg-white/10 text-white transition hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:opacity-60"
            onClick={onClose}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </header>

        <div className="min-h-0 overflow-y-auto px-4 py-4">
          <div className="rounded-lg border border-[#0f0f0f] bg-[#0f0f0f] px-4 py-4 text-white">
            <p className="text-[11px] font-black uppercase text-white/45">Lemma</p>
            <p className="mt-1 break-words text-3xl font-black leading-tight">
              {form.lemma || form.surface || '-'}
            </p>
            <p className="mt-2 text-sm font-bold text-white/65">
              {form.jpPron || '-'}
            </p>
          </div>

          <div className="mt-4 grid gap-3">
            {isAdmin ? (
              <label className="grid gap-1.5 text-sm font-black text-[var(--app-text)]">
                Lemma
                <input
                  aria-label="Lemma"
                  value={form.lemma ?? ''}
                  disabled={!canEditLemma}
                  onChange={(event) => setForm({ ...form, lemma: event.target.value })}
                  className="h-11 rounded-lg border border-[var(--app-border)] bg-white px-3 text-sm font-semibold outline-none transition focus:border-[var(--app-accent)] focus:ring-2 focus:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:bg-[#f3f3f3] disabled:text-[var(--app-muted)]"
                />
              </label>
            ) : null}

            <div className="grid gap-1.5 text-sm font-black text-[var(--app-text)]">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>한국어 뜻</span>
                {onFetchMeaning ? (
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      disabled={!canEditMeaning}
                      className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-[#2e2d2d] bg-white px-2.5 text-xs font-black text-[var(--app-text)] transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:border-[var(--app-border)] disabled:text-[var(--app-muted)] disabled:opacity-60"
                      onClick={() => void handleFetchMeaning('replace')}
                    >
                      <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                      {isFetchingMeaning ? '가져오는 중' : '뜻 대체'}
                    </button>
                    <button
                      type="button"
                      disabled={!canEditMeaning}
                      className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-[#2e2d2d] bg-white px-2.5 text-xs font-black text-[var(--app-text)] transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:border-[var(--app-border)] disabled:text-[var(--app-muted)] disabled:opacity-60"
                      onClick={() => void handleFetchMeaning('append')}
                    >
                      <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                      {isFetchingMeaning ? '가져오는 중' : '뜻 추가'}
                    </button>
                  </div>
                ) : null}
              </div>
              {isAdmin ? (
                <input
                  aria-label="한국어 뜻"
                  value={form.krMean}
                  disabled={!canEditMeaning}
                  onChange={(event) => setForm({ ...form, krMean: event.target.value })}
                  className="h-11 rounded-lg border border-[var(--app-border)] bg-white px-3 text-sm font-semibold outline-none transition focus:border-[var(--app-accent)] focus:ring-2 focus:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:bg-[#f3f3f3] disabled:text-[var(--app-muted)]"
                />
              ) : (
                <div className="min-h-11 rounded-lg border border-[var(--app-border)] bg-[#f7f7f7] px-3 py-2.5 text-sm font-semibold text-[var(--app-muted)]">
                  {form.krMean || '-'}
                </div>
              )}
            </div>

            <div className="grid gap-2 rounded-lg border border-[var(--app-border)] bg-[#fafafa] p-3">
              <label className="grid gap-1.5 text-sm font-black text-[var(--app-text)]">
                아는 정도 (0~100)
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={reading}
                  disabled={!canEditReading}
                  onChange={(event) => updateReading(Number(event.target.value))}
                  className="h-11 rounded-lg border border-[var(--app-border)] bg-white px-3 text-sm font-semibold outline-none transition focus:border-[var(--app-accent)] focus:ring-2 focus:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:bg-[#f3f3f3] disabled:text-[var(--app-muted)]"
                />
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[-10, 3, 25].map((delta) => (
                  <button
                    key={delta}
                    type="button"
                    disabled={!canEditReading}
                    className="h-9 rounded-lg border border-[#2e2d2d] bg-white px-2 text-sm font-black text-[var(--app-text)] transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:border-[var(--app-border)] disabled:text-[var(--app-muted)] disabled:opacity-60"
                    onClick={() => updateReading(reading + delta)}
                  >
                    {delta > 0 ? `+${delta}` : delta}
                  </button>
                ))}
              </div>
              {!hasPersistableWord ? (
                <p className="text-xs font-bold text-[var(--app-muted)]">
                  저장할 수 있는 형태소 정보가 없습니다.
                </p>
              ) : null}
            </div>
            {submitError ? (
              <p className="text-xs font-black text-[var(--app-accent)]">
                {submitError}
              </p>
            ) : null}
          </div>
        </div>

        <footer className="flex flex-col gap-2 border-t border-[var(--app-border)] bg-[#fafafa] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          {showDeleteButton ? (
            <button
              type="button"
              disabled={isBusy}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-[#ffd1d1] bg-white px-3 text-sm font-black text-[var(--app-accent)] transition hover:bg-[var(--app-accent-soft)] disabled:cursor-not-allowed disabled:border-[var(--app-border)] disabled:text-[var(--app-muted)] disabled:opacity-60"
              onClick={handleDelete}
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
              삭제
            </button>
          ) : (
            <span />
          )}
          <div className="flex gap-2 sm:justify-end">
            <button
              type="button"
              disabled={isBusy}
              className="inline-flex h-10 flex-1 items-center justify-center rounded-lg border border-[var(--app-border)] bg-white px-4 text-sm font-black transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:opacity-60 sm:flex-none"
              onClick={onClose}
            >
              취소
            </button>
            <button
              type="button"
              disabled={!canSubmit}
              className="inline-flex h-10 flex-1 items-center justify-center gap-2 rounded-lg border border-[#b02c2c] bg-[var(--app-accent)] px-4 text-sm font-black text-white transition hover:bg-[var(--app-accent-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:border-[var(--app-border)] disabled:bg-[#d1d1d1] sm:flex-none"
              onClick={handleSubmit}
            >
              <Save className="h-4 w-4" aria-hidden="true" />
              {isSubmitting ? '저장 중' : '저장'}
            </button>
          </div>
        </footer>
      </section>
    </div>
  );

  return createPortal(body, document.body);
}
