import { Plus, Wand2 } from 'lucide-react';
import { WordHighlighter } from '../../../components/WordHighlighter';
import { WordInputModal } from '../../../components/WordInputModal';
import { useExampleEditor } from '../ExampleEditorContext';

export function WordGenerationPanel() {
  const { session, words } = useExampleEditor();

  return (
    <section className="rounded-lg border border-[var(--app-border)] bg-[var(--app-panel)] p-4 shadow-sm">
      <div className="flex flex-col gap-2 border-b border-[var(--app-border)] pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-black uppercase text-[var(--app-accent)]">Words</p>
          <h2 className="mt-1 text-xl font-black text-[var(--app-text)]">단어 생성</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={words.cannotExtract}
            className={[
              'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
              words.cannotExtract
                ? 'border-[var(--app-border)] bg-[#f3f3f3] text-[var(--app-muted)] opacity-70'
                : 'border-[#2e2d2d] bg-white text-[var(--app-text)] hover:bg-[#f3f3f3]',
            ].join(' ')}
            onClick={() => {
              void words.extract();
            }}
          >
            <Wand2 className="h-4 w-4" aria-hidden="true" />
            {!session.authReady ? '인증 확인 중' : words.isExtracting ? '추출 중' : '형태소 추출'}
          </button>
          <button
            type="button"
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-black transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            onClick={words.openNewWordModal}
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            단어 모달
          </button>
        </div>
      </div>

      <div className="mt-4">
        <WordHighlighter
          words={words.items}
          selectedWordId={words.selectedWordId}
          emptyText="추출된 형태소가 없습니다."
          onWordSelect={(word) => words.openWordModal(word.id)}
        />
        {words.extractionError ? (
          <p className="mt-2 text-xs font-black text-[var(--app-accent)]">
            {words.extractionError}
          </p>
        ) : null}
      </div>

      <WordInputModal
        isOpen={words.isModalOpen}
        word={words.selectedWord}
        isAdmin={session.isAdmin}
        canSaveSkill={words.selectedWordCanSaveSkill}
        onClose={words.closeModal}
        onSubmit={words.submitWord}
        onDelete={session.isAdmin ? words.deleteWord : undefined}
        onFetchMeaning={
          session.isAdmin && words.selectedWord ? words.fetchSelectedWordMeaning : undefined
        }
      />
    </section>
  );
}
