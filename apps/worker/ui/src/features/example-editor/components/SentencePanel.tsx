import { Languages, ListFilter, Save, Shuffle, Sparkles, Wand2 } from 'lucide-react';
import type { ExampleDraft } from '../types';
import { useExampleEditor } from '../ExampleEditorContext';

const inputClass =
  'min-h-11 w-full rounded-lg border border-[var(--app-border)] bg-white px-3 py-2 text-sm font-semibold text-[var(--app-text)] outline-none transition placeholder:text-[#9a9a9a] focus:border-[var(--app-accent)] focus:ring-2 focus:ring-[var(--app-focus)]';
const promptClass =
  'min-h-24 w-full rounded-lg border border-[var(--app-border)] bg-white px-3 py-2 text-sm font-semibold text-[var(--app-text)] outline-none transition placeholder:text-[#9a9a9a] focus:border-[var(--app-accent)] focus:ring-2 focus:ring-[var(--app-focus)]';

export function SentencePanel() {
  const { draft, sentence, save } = useExampleEditor();
  const currentDraft = draft.value;
  const generatedText = currentDraft.generatedSentence.trim();
  const generatedWordCount = generatedText ? generatedText.split(/\s+/).length : 0;
  const isOverLimit = generatedWordCount > 10;
  const cannotGenerateSentence =
    sentence.isGenerating || !currentDraft.seedWord.trim();
  const cannotTranslateMeaning = sentence.isTranslating || !currentDraft.generatedSentence.trim();

  const updateDraft = (field: keyof ExampleDraft, value: string) => {
    draft.set({
      ...currentDraft,
      [field]: value,
    });
  };

  return (
    <section className="rounded-lg border border-[var(--app-border)] bg-[var(--app-panel)] p-4 shadow-sm">
      <div className="flex flex-col gap-2 border-b border-[var(--app-border)] pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-black uppercase text-[var(--app-accent)]">Sentence</p>
          <h1 className="mt-1 text-xl font-black text-[var(--app-text)]">문장 패널</h1>
        </div>
        <button
          type="button"
          disabled={!save.canSave || save.isSaving}
          className={[
            'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-4 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
            save.canSave && !save.isSaving
              ? 'border-[#b02c2c] bg-[var(--app-accent)] text-white hover:bg-[var(--app-accent-strong)]'
              : 'border-[var(--app-border)] bg-[#d1d1d1] text-white opacity-70',
          ].join(' ')}
          onClick={() => {
            void save.prepare();
          }}
        >
          <Save className="h-4 w-4" aria-hidden="true" />
          {save.isSaving ? '저장 준비 중' : '문장 단위 저장'}
        </button>
      </div>
      {save.panelError ? (
        <p className="mt-3 text-xs font-black text-[var(--app-accent)]">
          {save.panelError}
        </p>
      ) : null}

      <div className="mt-4 grid gap-4">
        <label className="grid gap-1.5 text-sm font-black text-[var(--app-text)]">
          <span className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span>기준 일본어 문장</span>
            <span className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={sentence.isPickingRandomExample || sentence.isLoadingLowSimilarityExamples}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-xs font-black text-[var(--app-text)] transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:border-[var(--app-border)] disabled:text-[var(--app-muted)] disabled:opacity-70"
                onClick={() => {
                  void sentence.pickRandomExample();
                }}
              >
                <Shuffle className="h-3.5 w-3.5" aria-hidden="true" />
                {sentence.isPickingRandomExample ? '가져오는 중' : '무작위 문장'}
              </button>
              <button
                type="button"
                disabled={sentence.isPickingRandomExample || sentence.isLoadingLowSimilarityExamples}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-xs font-black text-[var(--app-text)] transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:border-[var(--app-border)] disabled:text-[var(--app-muted)] disabled:opacity-70"
                onClick={() => {
                  void sentence.openLowSimilarityPicker();
                }}
              >
                <ListFilter className="h-3.5 w-3.5" aria-hidden="true" />
                {sentence.isLoadingLowSimilarityExamples ? '불러오는 중' : '낮은 유사도'}
              </button>
            </span>
          </span>
          <textarea
            value={currentDraft.sourceSentence}
            rows={3}
            placeholder="例: 朝ごはんにおにぎりを食べます。"
            className={inputClass}
            onChange={(event) => updateDraft('sourceSentence', event.target.value)}
          />
          {sentence.randomExampleError ? (
            <span className="text-xs font-black text-[var(--app-accent)]">
              {sentence.randomExampleError}
            </span>
          ) : null}
          {sentence.lowSimilarityExampleError ? (
            <span className="text-xs font-black text-[var(--app-accent)]">
              {sentence.lowSimilarityExampleError}
            </span>
          ) : null}
        </label>

        <label className="grid gap-1.5 text-sm font-black text-[var(--app-text)]">
          <span className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span>일본어 단어</span>
            <span className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={sentence.isPickingRandomWord || sentence.isLoadingLowExampleCountWords}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-xs font-black text-[var(--app-text)] transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:border-[var(--app-border)] disabled:text-[var(--app-muted)] disabled:opacity-70"
                onClick={() => {
                  void sentence.pickRandomWord();
                }}
              >
                <Shuffle className="h-3.5 w-3.5" aria-hidden="true" />
                {sentence.isPickingRandomWord ? '가져오는 중' : '무작위 단어'}
              </button>
              <button
                type="button"
                disabled={sentence.isPickingRandomWord || sentence.isLoadingLowExampleCountWords}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-white px-3 text-xs font-black text-[var(--app-text)] transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:border-[var(--app-border)] disabled:text-[var(--app-muted)] disabled:opacity-70"
                onClick={() => {
                  void sentence.openLowExampleCountWordPicker();
                }}
              >
                <ListFilter className="h-3.5 w-3.5" aria-hidden="true" />
                {sentence.isLoadingLowExampleCountWords ? '불러오는 중' : '예문 적은 단어'}
              </button>
            </span>
          </span>
          <input
            value={currentDraft.seedWord}
            placeholder="例: おにぎり"
            className={inputClass}
            onChange={(event) => updateDraft('seedWord', event.target.value)}
          />
          {sentence.randomWordError ? (
            <span className="text-xs font-black text-[var(--app-accent)]">
              {sentence.randomWordError}
            </span>
          ) : null}
          {sentence.lowExampleCountWordError ? (
            <span className="text-xs font-black text-[var(--app-accent)]">
              {sentence.lowExampleCountWordError}
            </span>
          ) : null}
        </label>

        <div className="grid gap-1.5 text-sm font-black text-[var(--app-text)]">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <label htmlFor="generated-sentence">일본어 문장 생성/수정</label>
            <button
              type="button"
              disabled={cannotGenerateSentence}
              className={[
                'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                cannotGenerateSentence
                  ? 'border-[var(--app-border)] bg-[#f3f3f3] text-[var(--app-muted)] opacity-70'
                  : 'border-[#2e2d2d] bg-white text-[var(--app-text)] hover:bg-[#f3f3f3]',
              ].join(' ')}
              onClick={() => {
                void sentence.generate();
              }}
            >
              <Wand2 className="h-4 w-4" aria-hidden="true" />
              {sentence.isGenerating ? '생성 중' : '다음 문장 생성'}
            </button>
          </div>
          <textarea
            id="generated-sentence"
            value={currentDraft.generatedSentence}
            rows={3}
            placeholder="10 단어 이하"
            className={[
              inputClass,
              isOverLimit ? 'border-[var(--app-accent)] ring-2 ring-[var(--app-focus)]' : '',
            ].join(' ')}
            onChange={(event) => updateDraft('generatedSentence', event.target.value)}
          />
          <span
            className={[
              'text-xs font-black',
              isOverLimit ? 'text-[var(--app-accent)]' : 'text-[var(--app-muted)]',
            ].join(' ')}
          >
            {generatedWordCount}/10 단어
          </span>
          {sentence.generationError ? (
            <span className="text-xs font-black text-[var(--app-accent)]">
              {sentence.generationError}
            </span>
          ) : null}
        </div>

        <div className="grid gap-1.5 text-sm font-black text-[var(--app-text)]">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <label htmlFor="kr-meaning">한국어 뜻 생성/수정</label>
            <button
              type="button"
              disabled={cannotTranslateMeaning}
              className={[
                'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                cannotTranslateMeaning
                  ? 'border-[var(--app-border)] bg-[#f3f3f3] text-[var(--app-muted)] opacity-70'
                  : 'border-[#2e2d2d] bg-white text-[var(--app-text)] hover:bg-[#f3f3f3]',
              ].join(' ')}
              onClick={() => {
                void sentence.translate();
              }}
            >
              <Languages className="h-4 w-4" aria-hidden="true" />
              {sentence.isTranslating ? '번역 중' : '한국어 번역'}
            </button>
          </div>
          <textarea
            id="kr-meaning"
            value={currentDraft.krMeaning}
            rows={3}
            placeholder="한국어 뜻"
            className={inputClass}
            onChange={(event) => updateDraft('krMeaning', event.target.value)}
          />
          {sentence.translationError ? (
            <span className="text-xs font-black text-[var(--app-accent)]">
              {sentence.translationError}
            </span>
          ) : null}
        </div>

        <div className="grid gap-3 text-sm font-black text-[var(--app-text)]">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p>SDXL 프롬프트 생성/수정</p>
            <button
              type="button"
              disabled={sentence.cannotGeneratePrompt}
              className={[
                'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                sentence.cannotGeneratePrompt
                  ? 'border-[var(--app-border)] bg-[#f3f3f3] text-[var(--app-muted)]'
                  : 'border-[#2e2d2d] bg-white text-[var(--app-text)] hover:bg-[#f3f3f3]',
              ].join(' ')}
              onClick={() => {
                void sentence.generatePrompt();
              }}
            >
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              {sentence.isGeneratingPrompt ? '생성 중' : 'LLM으로 프롬프트 생성'}
            </button>
          </div>
          {sentence.promptError ? (
            <span className="text-xs font-black text-[var(--app-accent)]">
              {sentence.promptError}
            </span>
          ) : null}

          <div className="grid gap-3 lg:grid-cols-2">
            <label className="grid gap-1.5">
              SDXL positive prompt
              <textarea
                value={currentDraft.positivePrompt}
                placeholder="positive prompt"
                className={promptClass}
                onChange={(event) => draft.setField('positivePrompt', event.target.value)}
              />
            </label>
            <label className="grid gap-1.5">
              SDXL negative prompt
              <textarea
                value={currentDraft.negativePrompt}
                placeholder="negative prompt"
                className={promptClass}
                onChange={(event) => draft.setField('negativePrompt', event.target.value)}
              />
            </label>
          </div>
        </div>
      </div>
    </section>
  );
}
