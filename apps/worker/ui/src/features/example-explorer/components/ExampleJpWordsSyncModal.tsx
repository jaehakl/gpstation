import { Play, RefreshCw, X } from 'lucide-react';
import type { FormEvent } from 'react';
import { useState } from 'react';
import { createPortal } from 'react-dom';
import { useExampleExplorer } from '../ExampleExplorerContext';

type ExampleJpWordsSyncModalProps = {
  isOpen: boolean;
  onClose: () => void;
};

export function ExampleJpWordsSyncModal({
  isOpen,
  onClose,
}: ExampleJpWordsSyncModalProps) {
  const { list } = useExampleExplorer();

  if (!isOpen) {
    return null;
  }

  return (
    <ExampleJpWordsSyncModalBody
      isSyncing={list.isSyncingJpWords}
      summaryMessage={list.syncJpWordsMessage}
      errorMessage={list.syncJpWordsError}
      batchMessages={list.syncJpWordsBatchMessages}
      onClose={onClose}
      onSubmit={list.syncJpWords}
    />
  );
}

type ExampleJpWordsSyncModalBodyProps = {
  isSyncing: boolean;
  summaryMessage: string | null;
  errorMessage: string | null;
  batchMessages: string[];
  onClose: () => void;
  onSubmit: (range: { startId: number; endId: number }) => Promise<void>;
};

function ExampleJpWordsSyncModalBody({
  isSyncing,
  summaryMessage,
  errorMessage,
  batchMessages,
  onClose,
  onSubmit,
}: ExampleJpWordsSyncModalBodyProps) {
  const [startIdInput, setStartIdInput] = useState('');
  const [endIdInput, setEndIdInput] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);
  const hasResult = Boolean(summaryMessage || errorMessage || batchMessages.length);
  const canSubmit = !isSyncing;

  const closeModal = () => {
    if (!isSyncing) {
      onClose();
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }

    const startId = Number(startIdInput);
    const endId = Number(endIdInput);
    if (!startIdInput.trim() || !endIdInput.trim()) {
      setValidationError('시작 ID와 끝 ID를 모두 입력해 주세요.');
      return;
    }
    if (
      !Number.isInteger(startId)
      || !Number.isInteger(endId)
      || startId < 1
      || endId < 1
    ) {
      setValidationError('ID는 1 이상의 정수로 입력해 주세요.');
      return;
    }
    if (startId > endId) {
      setValidationError('시작 ID는 끝 ID보다 클 수 없습니다.');
      return;
    }

    setValidationError(null);
    void onSubmit({ startId, endId });
  };

  const body = (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 px-4 py-6">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="example-jp-words-sync-modal-title"
        className="flex max-h-full w-full max-w-xl flex-col overflow-hidden rounded-lg border border-[#0f0f0f] bg-white shadow-[var(--app-shadow)]"
      >
        <header className="flex min-h-14 items-center gap-3 border-b border-[var(--app-border)] bg-[#0f0f0f] px-4 text-white">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-black uppercase text-white/55">Examples</p>
            <h2 id="example-jp-words-sync-modal-title" className="truncate text-lg font-black">
              JpWords 동기화
            </h2>
          </div>
          <button
            type="button"
            aria-label="JpWords 동기화 모달 닫기"
            title="닫기"
            disabled={isSyncing}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/20 bg-white/10 text-white transition hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:opacity-60"
            onClick={closeModal}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </header>

        <form className="flex min-h-0 flex-1 flex-col" onSubmit={handleSubmit}>
          <div className="min-h-0 overflow-y-auto px-4 py-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1.5 text-sm font-black text-[var(--app-text)]">
                시작 ID
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={startIdInput}
                  disabled={isSyncing}
                  onChange={(event) => setStartIdInput(event.target.value)}
                  className="h-11 rounded-lg border border-[var(--app-border)] bg-white px-3 text-sm font-semibold outline-none transition focus:border-[var(--app-accent)] focus:ring-2 focus:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:bg-[#f3f3f3] disabled:text-[var(--app-muted)]"
                />
              </label>
              <label className="grid gap-1.5 text-sm font-black text-[var(--app-text)]">
                끝 ID
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={endIdInput}
                  disabled={isSyncing}
                  onChange={(event) => setEndIdInput(event.target.value)}
                  className="h-11 rounded-lg border border-[var(--app-border)] bg-white px-3 text-sm font-semibold outline-none transition focus:border-[var(--app-accent)] focus:ring-2 focus:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:bg-[#f3f3f3] disabled:text-[var(--app-muted)]"
                />
              </label>
            </div>

            {validationError ? (
              <p className="mt-3 text-xs font-black text-[var(--app-accent)]">
                {validationError}
              </p>
            ) : null}

            <div className="mt-4 rounded-lg border border-[var(--app-border)] bg-[#fafafa] p-3">
              <div className="flex items-center gap-2 text-sm font-black text-[var(--app-text)]">
                <RefreshCw
                  className={[
                    'h-4 w-4',
                    isSyncing ? 'animate-spin' : '',
                  ].join(' ')}
                  aria-hidden="true"
                />
                {summaryMessage ?? (isSyncing ? '동기화 중입니다.' : '아직 실행하지 않았습니다.')}
              </div>
              {errorMessage ? (
                <p className="mt-2 text-xs font-black text-[var(--app-accent)]">
                  {errorMessage}
                </p>
              ) : null}
            </div>

            <div className="mt-4">
              <p className="text-xs font-black uppercase text-[var(--app-muted)]">
                Batch Log
              </p>
              <div className="mt-2 max-h-56 overflow-y-auto rounded-lg border border-[var(--app-border)] bg-white">
                {batchMessages.length ? (
                  batchMessages.map((message, index) => (
                    <p
                      key={`${index}-${message}`}
                      className="border-b border-[var(--app-border)] px-3 py-2 text-sm font-bold text-[var(--app-text)] last:border-b-0"
                    >
                      {message}
                    </p>
                  ))
                ) : (
                  <p className="px-3 py-8 text-center text-sm font-bold text-[var(--app-muted)]">
                    배치별 메시지가 여기에 표시됩니다.
                  </p>
                )}
              </div>
            </div>
          </div>

          <footer className="flex flex-col gap-2 border-t border-[var(--app-border)] bg-[#fafafa] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <button
              type="button"
              disabled={isSyncing}
              className="inline-flex h-10 items-center justify-center rounded-lg border border-[var(--app-border)] bg-white px-4 text-sm font-black transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:opacity-60"
              onClick={closeModal}
            >
              {hasResult ? '닫기' : '취소'}
            </button>
            <button
              type="submit"
              disabled={!canSubmit}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-[#b02c2c] bg-[var(--app-accent)] px-4 text-sm font-black text-white transition hover:bg-[var(--app-accent-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:border-[var(--app-border)] disabled:bg-[#d1d1d1]"
            >
              <Play className="h-4 w-4" aria-hidden="true" />
              {isSyncing ? '동기화 중' : '동기화 시작'}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );

  return createPortal(body, document.body);
}
