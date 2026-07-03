import { createPortal } from 'react-dom';
import { Check, X } from 'lucide-react';
import { useExampleEditor } from '../ExampleEditorContext';

function formatSimilarityScore(score: number | null) {
  return typeof score === 'number' ? `${(score * 100).toFixed(1)}%` : '-';
}

export function LowSimilarityExamplePickerModal() {
  const { sentence } = useExampleEditor();

  if (!sentence.isLowSimilarityPickerOpen) {
    return null;
  }

  const body = (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 px-4 py-6"
      onClick={sentence.closeLowSimilarityPicker}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="low-similarity-example-picker-title"
        className="flex max-h-full w-full max-w-3xl flex-col overflow-hidden rounded-lg border border-[#0f0f0f] bg-white shadow-[var(--app-shadow)]"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex min-h-14 items-center gap-3 border-b border-[var(--app-border)] bg-[#0f0f0f] px-4 text-white">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-black uppercase text-white/55">Similarity</p>
            <h2 id="low-similarity-example-picker-title" className="truncate text-lg font-black">
              낮은 유사도 문장
            </h2>
          </div>
          <button
            type="button"
            aria-label="낮은 유사도 문장 모달 닫기"
            title="닫기"
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/20 bg-white/10 text-white transition hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            onClick={sentence.closeLowSimilarityPicker}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </header>

        <div className="min-h-0 overflow-y-auto px-4 py-4">
          {sentence.lowSimilarityExampleError ? (
            <div className="flex min-h-44 items-center justify-center rounded-lg border border-[#f1b5b5] bg-[#fff5f5] px-4 text-center text-sm font-black text-[var(--app-accent)]">
              {sentence.lowSimilarityExampleError}
            </div>
          ) : sentence.isLoadingLowSimilarityExamples ? (
            <div className="flex min-h-44 items-center justify-center rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa] px-4 text-center text-sm font-bold text-[var(--app-muted)]">
              후보를 불러오는 중입니다.
            </div>
          ) : sentence.lowSimilarityExamples.length === 0 ? (
            <div className="flex min-h-44 items-center justify-center rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa] px-4 text-center text-sm font-bold text-[var(--app-muted)]">
              표시할 후보가 없습니다.
            </div>
          ) : (
            <div className="grid gap-2">
              {sentence.lowSimilarityExamples.map((candidate) => (
                <button
                  key={candidate.id}
                  type="button"
                  className="grid gap-3 rounded-lg border border-[var(--app-border)] bg-white p-3 text-left transition hover:border-[#2e2d2d] hover:bg-[#fafafa] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                  onClick={() => sentence.selectLowSimilarityExample(candidate)}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-black uppercase text-[var(--app-muted)]">
                      Example #{candidate.id}
                    </span>
                    <span className="inline-flex items-center gap-1.5 rounded-lg border border-[#2e2d2d] bg-[#f3f3f3] px-2 py-1 text-xs font-black text-[var(--app-text)]">
                      <Check className="h-3.5 w-3.5" aria-hidden="true" />
                      similarity {formatSimilarityScore(candidate.similarityScore)}
                    </span>
                  </div>
                  <p className="break-words text-base font-black leading-6 text-[var(--app-text)]">
                    {candidate.jpText}
                  </p>
                  <div className="rounded-lg border border-[var(--app-border)] bg-[#fafafa] px-3 py-2">
                    <p className="text-[11px] font-black uppercase text-[var(--app-muted)]">
                      Target {candidate.targetId == null ? '-' : `#${candidate.targetId}`}
                    </p>
                    <p className="mt-1 break-words text-sm font-bold leading-5 text-[var(--app-muted)]">
                      {candidate.targetJpText ?? 'target 문장을 불러오지 못했습니다.'}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <footer className="flex justify-end border-t border-[var(--app-border)] bg-[#fafafa] px-4 py-3">
          <button
            type="button"
            className="inline-flex h-10 items-center justify-center rounded-lg border border-[var(--app-border)] bg-white px-4 text-sm font-black transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            onClick={sentence.closeLowSimilarityPicker}
          >
            닫기
          </button>
        </footer>
      </section>
    </div>
  );

  return createPortal(body, document.body);
}
