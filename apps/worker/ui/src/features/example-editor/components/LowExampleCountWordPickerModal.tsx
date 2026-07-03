import { createPortal } from 'react-dom';
import { Check, LoaderCircle, Trash2, X } from 'lucide-react';
import { useExampleEditor } from '../ExampleEditorContext';

export function LowExampleCountWordPickerModal() {
  const { sentence, session } = useExampleEditor();

  if (!sentence.isLowExampleCountWordPickerOpen) {
    return null;
  }

  const body = (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 px-4 py-6"
      onClick={sentence.closeLowExampleCountWordPicker}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="low-example-count-word-picker-title"
        className="flex max-h-full w-full max-w-2xl flex-col overflow-hidden rounded-lg border border-[#0f0f0f] bg-white shadow-[var(--app-shadow)]"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex min-h-14 items-center gap-3 border-b border-[var(--app-border)] bg-[#0f0f0f] px-4 text-white">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-black uppercase text-white/55">Jp Word</p>
            <h2 id="low-example-count-word-picker-title" className="truncate text-lg font-black">
              예문 수 적은 단어
            </h2>
          </div>
          <button
            type="button"
            aria-label="예문 수 적은 단어 모달 닫기"
            title="닫기"
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/20 bg-white/10 text-white transition hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            onClick={sentence.closeLowExampleCountWordPicker}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </header>

        <div className="min-h-0 overflow-y-auto px-4 py-4">
          {sentence.lowExampleCountWordError ? (
            <div className="mb-3 rounded-lg border border-[#f1b5b5] bg-[#fff5f5] px-4 py-3 text-sm font-black text-[var(--app-accent)]">
              {sentence.lowExampleCountWordError}
            </div>
          ) : null}

          {sentence.isLoadingLowExampleCountWords ? (
            <div className="flex min-h-44 items-center justify-center rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa] px-4 text-center text-sm font-bold text-[var(--app-muted)]">
              후보를 불러오는 중입니다.
            </div>
          ) : sentence.lowExampleCountWords.length === 0 ? (
            <div className="flex min-h-44 items-center justify-center rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa] px-4 text-center text-sm font-bold text-[var(--app-muted)]">
              표시할 후보가 없습니다.
            </div>
          ) : (
            <div className="grid gap-2">
              {sentence.lowExampleCountWords.map((candidate) => {
                const isDeleting = sentence.deletingLowExampleCountWordId === candidate.id;
                const deleteDisabled = sentence.deletingLowExampleCountWordId != null;

                return (
                  <div
                    key={candidate.id}
                    className="grid gap-3 rounded-lg border border-[var(--app-border)] bg-white p-3 text-left"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-black uppercase text-[var(--app-muted)]">
                        Word #{candidate.id}
                      </span>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center gap-1.5 rounded-lg border border-[#2e2d2d] bg-[#f3f3f3] px-2 py-1 text-xs font-black text-[var(--app-text)]">
                          <Check className="h-3.5 w-3.5" aria-hidden="true" />
                          examples {candidate.exampleCount}
                        </span>
                        {session.isAdmin ? (
                          <button
                            type="button"
                            disabled={deleteDisabled}
                            aria-label={
                              isDeleting
                                ? `${candidate.lemma} 단어 삭제 중`
                                : `${candidate.lemma} 단어 삭제`
                            }
                            title={isDeleting ? '삭제 중' : '단어 삭제'}
                            className={[
                              'inline-flex h-8 min-w-8 items-center justify-center gap-1.5 rounded-lg border px-2 text-xs font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                              deleteDisabled
                                ? 'border-[var(--app-border)] bg-[#f3f3f3] text-[var(--app-muted)] opacity-70'
                                : 'border-[#ffd1d1] bg-white text-[var(--app-accent)] hover:bg-[#fff4f4]',
                            ].join(' ')}
                            onClick={() => {
                              void sentence.deleteLowExampleCountWord(candidate.id);
                            }}
                          >
                            {isDeleting ? (
                              <>
                                <LoaderCircle className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                                삭제 중
                              </>
                            ) : (
                              <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                            )}
                          </button>
                        ) : null}
                      </div>
                    </div>
                    <button
                      type="button"
                      disabled={isDeleting}
                      aria-label={`${candidate.lemma} 단어 선택`}
                      className="grid gap-1 rounded-md text-left transition hover:bg-[#fafafa] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:opacity-70"
                      onClick={() => sentence.selectLowExampleCountWord(candidate)}
                    >
                      <p className="break-words text-xl font-black leading-6 text-[var(--app-text)]">
                        {candidate.lemma}
                      </p>
                      <p className="break-words text-sm font-bold leading-5 text-[var(--app-muted)]">
                        {candidate.krMean || '-'}
                      </p>
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <footer className="flex justify-end border-t border-[var(--app-border)] bg-[#fafafa] px-4 py-3">
          <button
            type="button"
            className="inline-flex h-10 items-center justify-center rounded-lg border border-[var(--app-border)] bg-white px-4 text-sm font-black transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            onClick={sentence.closeLowExampleCountWordPicker}
          >
            닫기
          </button>
        </footer>
      </section>
    </div>
  );

  return createPortal(body, document.body);
}
