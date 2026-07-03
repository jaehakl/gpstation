import { Languages, Save, Sparkles, Trash2 } from 'lucide-react';
import { WordHighlighter } from '../../../components/WordHighlighter';
import { WordInputModal } from '../../../components/WordInputModal';
import { useExampleExplorer } from '../ExampleExplorerContext';
import { ExplorerAudioPanel } from './ExplorerAudioPanel';
import { ExplorerImagePanel } from './ExplorerImagePanel';

const textareaClass =
  'min-h-24 w-full rounded-lg border border-[var(--app-border)] bg-white px-3 py-2 text-sm font-semibold text-[var(--app-text)] outline-none transition placeholder:text-[#9a9a9a] focus:border-[var(--app-accent)] focus:ring-2 focus:ring-[var(--app-focus)]';

export function ExampleDetailPanel() {
  const { detail, selectedExample, session, words } = useExampleExplorer();

  if (!selectedExample) {
    return (
      <section className="flex min-h-[520px] items-center justify-center rounded-lg border border-dashed border-[var(--app-border)] bg-[var(--app-panel)] px-6 py-10 text-center shadow-sm">
        <div>
          <p className="text-xs font-black uppercase text-[var(--app-accent)]">Detail</p>
          <h2 className="mt-2 text-2xl font-black text-[var(--app-text)]">
            예문을 선택하세요
          </h2>
          <p className="mt-2 text-sm font-bold text-[var(--app-muted)]">
            왼쪽 목록에서 행을 선택하면 상세 데이터가 표시됩니다.
          </p>
          {detail.deleteError ? (
            <p className="mt-3 text-xs font-black text-[var(--app-accent)]">
              {detail.deleteError}
            </p>
          ) : null}
          {detail.deleteMessage ? (
            <p className="mt-3 text-xs font-black text-[#167347]">
              {detail.deleteMessage}
            </p>
          ) : null}
        </div>
      </section>
    );
  }

  return (
    <div className="grid min-w-0 gap-4">
      <section className="rounded-lg border border-[var(--app-border)] bg-[var(--app-panel)] p-4 shadow-sm">
        <div className="flex flex-col gap-3 border-b border-[var(--app-border)] pb-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-black uppercase text-[var(--app-accent)]">Detail</p>
            <h2 className="mt-1 truncate text-xl font-black text-[var(--app-text)]">
              Example #{selectedExample.id ?? '-'}
            </h2>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <button
              type="button"
              disabled={!detail.canDelete}
              className={[
                'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-4 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                detail.canDelete
                  ? 'border-[#ffd1d1] bg-white text-[var(--app-accent)] hover:bg-[#fff4f4]'
                  : 'border-[var(--app-border)] bg-[#f3f3f3] text-[var(--app-muted)] opacity-70',
              ].join(' ')}
              onClick={() => {
                if (window.confirm('이 예문을 삭제할까요? 저장된 오디오와 오류 제보도 함께 삭제됩니다.')) {
                  void detail.deleteSelected();
                }
              }}
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
              {detail.isDeleting ? '삭제 중' : '삭제'}
            </button>
            <button
              type="button"
              disabled={!detail.canSave}
              className={[
                'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-4 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                detail.canSave
                  ? 'border-[#b02c2c] bg-[var(--app-accent)] text-white hover:bg-[var(--app-accent-strong)]'
                  : 'border-[var(--app-border)] bg-[#d1d1d1] text-white opacity-70',
              ].join(' ')}
              onClick={() => {
                void detail.save();
              }}
            >
              <Save className="h-4 w-4" aria-hidden="true" />
              {detail.isSaving ? '저장 중' : detail.isDirty ? '변경 저장' : '저장'}
            </button>
          </div>
        </div>

        <div className="mt-4 grid gap-4">
          <div>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-black text-[var(--app-text)]">일본어</p>
              {words.isExtracting ? (
                <span className="text-xs font-black text-[var(--app-muted)]">분석 중</span>
              ) : null}
            </div>
            <WordHighlighter
              words={words.items}
              selectedWordId={words.selectedWordId}
              emptyText={words.isExtracting ? '형태소를 분석하는 중입니다.' : '추출된 형태소가 없습니다.'}
              onWordSelect={(word) => words.openWordModal(word.id)}
            />
            {words.extractionError ? (
              <p className="mt-2 text-xs font-black text-[var(--app-accent)]">
                {words.extractionError}
              </p>
            ) : null}
          </div>

          <div className="grid gap-1.5 text-sm font-black text-[var(--app-text)]">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <label htmlFor="explorer-kr-text">한국어 뜻</label>
              <button
                type="button"
                disabled={detail.isTranslating}
                className={[
                  'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                  detail.isTranslating
                    ? 'border-[var(--app-border)] bg-[#f3f3f3] text-[var(--app-muted)] opacity-70'
                    : 'border-[#2e2d2d] bg-white text-[var(--app-text)] hover:bg-[#f3f3f3]',
                ].join(' ')}
                onClick={() => {
                  void detail.translate();
                }}
              >
                <Languages className="h-4 w-4" aria-hidden="true" />
                {detail.isTranslating ? '번역 중' : '한국어 번역'}
              </button>
            </div>
            <textarea
              id="explorer-kr-text"
              value={detail.form.krText}
              rows={3}
              placeholder="한국어 뜻"
              className={textareaClass}
              onChange={(event) => detail.setField('krText', event.target.value)}
            />
            {detail.translationError ? (
              <span className="text-xs font-black text-[var(--app-accent)]">
                {detail.translationError}
              </span>
            ) : null}
          </div>

          <div className="grid gap-3 text-sm font-black text-[var(--app-text)]">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p>SDXL 프롬프트</p>
              <button
                type="button"
                disabled={detail.isGeneratingPrompt}
                className={[
                  'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                  detail.isGeneratingPrompt
                    ? 'border-[var(--app-border)] bg-[#f3f3f3] text-[var(--app-muted)]'
                    : 'border-[#2e2d2d] bg-white text-[var(--app-text)] hover:bg-[#f3f3f3]',
                ].join(' ')}
                onClick={() => {
                  void detail.generatePrompt();
                }}
              >
                <Sparkles className="h-4 w-4" aria-hidden="true" />
                {detail.isGeneratingPrompt ? '생성 중' : 'LLM으로 생성'}
              </button>
            </div>
            {detail.promptError ? (
              <span className="text-xs font-black text-[var(--app-accent)]">
                {detail.promptError}
              </span>
            ) : null}

            <div className="grid gap-3 lg:grid-cols-2">
              <label className="grid gap-1.5">
                Positive prompt
                <textarea
                  value={detail.form.prompt}
                  placeholder="positive prompt"
                  className={textareaClass}
                  onChange={(event) => detail.setField('prompt', event.target.value)}
                />
              </label>
              <label className="grid gap-1.5">
                Negative prompt
                <textarea
                  value={detail.form.negativePrompt}
                  placeholder="negative prompt"
                  className={textareaClass}
                  onChange={(event) => detail.setField('negativePrompt', event.target.value)}
                />
              </label>
            </div>
          </div>

          {detail.saveError ? (
            <p className="text-xs font-black text-[var(--app-accent)]">
              {detail.saveError}
            </p>
          ) : null}
          {detail.deleteError ? (
            <p className="text-xs font-black text-[var(--app-accent)]">
              {detail.deleteError}
            </p>
          ) : null}
          {detail.saveMessage ? (
            <p className="text-xs font-black text-[#167347]">{detail.saveMessage}</p>
          ) : null}
          {detail.deleteMessage ? (
            <p className="text-xs font-black text-[#167347]">{detail.deleteMessage}</p>
          ) : null}
          {!session.isAdmin ? (
            <p className="text-xs font-bold text-[var(--app-muted)]">
              admin 권한이 있어야 예문과 파일을 저장할 수 있습니다.
            </p>
          ) : null}
        </div>
      </section>

      <ExplorerAudioPanel />
      <ExplorerImagePanel />

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
    </div>
  );
}
