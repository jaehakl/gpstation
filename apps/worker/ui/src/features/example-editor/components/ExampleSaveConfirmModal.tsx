import { createPortal } from 'react-dom';
import { Plus, Save, X } from 'lucide-react';
import { useExampleEditor } from '../ExampleEditorContext';

export function ExampleSaveConfirmModal() {
  const { save } = useExampleEditor();
  const pending = save.pending;

  if (!pending) {
    return null;
  }

  const candidate = pending.candidate;
  const candidateId = candidate?.id ?? null;
  const scoreLabel = candidate ? `${(candidate.score * 100).toFixed(1)}%` : null;

  const body = (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 px-4 py-6"
      onClick={() => {
        if (!save.isConfirming) {
          save.closeModal();
        }
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="example-save-confirm-modal-title"
        className="flex max-h-full w-full max-w-2xl flex-col overflow-hidden rounded-lg border border-[#0f0f0f] bg-white shadow-[var(--app-shadow)]"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex min-h-14 items-center gap-3 border-b border-[var(--app-border)] bg-[#0f0f0f] px-4 text-white">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-black uppercase text-white/55">Example Save</p>
            <h2 id="example-save-confirm-modal-title" className="truncate text-lg font-black">
              예문 저장 확인
            </h2>
          </div>
          <button
            type="button"
            aria-label="예문 저장 확인 모달 닫기"
            title="닫기"
            disabled={save.isConfirming}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/20 bg-white/10 text-white transition hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:opacity-60"
            onClick={save.closeModal}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </header>

        <div className="min-h-0 overflow-y-auto px-4 py-4">
          <div className="grid gap-3 rounded-lg border border-[var(--app-border)] bg-[#fafafa] p-3">
            <p className="text-[11px] font-black uppercase text-[var(--app-muted)]">저장할 문장</p>
            <p className="break-words text-base font-black text-[var(--app-text)]">{pending.jpText}</p>
            <p className="break-words text-sm font-bold text-[var(--app-muted)]">{pending.krText}</p>
          </div>

          <div className="mt-4 grid gap-3 rounded-lg border border-[#0f0f0f] bg-white p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-[11px] font-black uppercase text-[var(--app-muted)]">
                유사 문장
              </p>
              {scoreLabel ? (
                <span className="rounded-lg border border-[#2e2d2d] bg-[#f3f3f3] px-2 py-1 text-xs font-black text-[var(--app-text)]">
                  similarity {scoreLabel}
                </span>
              ) : null}
            </div>

            {candidate ? (
              <div className="grid gap-2">
                <p className="break-words text-base font-black text-[var(--app-text)]">
                  {candidate.example.jp_text}
                </p>
                <p className="break-words text-sm font-bold text-[var(--app-muted)]">
                  {candidate.example.kr_text}
                </p>
              </div>
            ) : (
              <div className="flex min-h-24 items-center justify-center rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa] px-4 text-center text-sm font-bold text-[var(--app-muted)]">
                유사 문장이 없습니다. 새 Example로 저장할 수 있습니다.
              </div>
            )}
          </div>

          {save.modalError ? (
            <p className="mt-3 text-xs font-black text-[var(--app-accent)]">
              {save.modalError}
            </p>
          ) : null}
        </div>

        <footer className="flex flex-col gap-2 border-t border-[var(--app-border)] bg-[#fafafa] px-4 py-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            disabled={save.isConfirming}
            className="inline-flex h-10 items-center justify-center rounded-lg border border-[var(--app-border)] bg-white px-4 text-sm font-black transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:opacity-60"
            onClick={save.closeModal}
          >
            취소
          </button>
          <button
            type="button"
            disabled={save.isConfirming}
            className={[
              'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-4 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:opacity-60',
              candidateId == null
                ? 'border-[#b02c2c] bg-[var(--app-accent)] text-white hover:bg-[var(--app-accent-strong)]'
                : 'border-[#2e2d2d] bg-white text-[var(--app-text)] hover:bg-[#f3f3f3]',
            ].join(' ')}
            onClick={() => {
              void save.confirm();
            }}
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            새 Example 생성
          </button>
        </footer>
      </section>
    </div>
  );

  return createPortal(body, document.body);
}
