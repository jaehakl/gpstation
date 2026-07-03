import { Sparkles } from 'lucide-react';
import { AudioPanel } from './components/AudioPanel';
import { ExampleSaveConfirmModal } from './components/ExampleSaveConfirmModal';
import { ImagePanel } from './components/ImagePanel';
import { LowExampleCountWordPickerModal } from './components/LowExampleCountWordPickerModal';
import { LowSimilarityExamplePickerModal } from './components/LowSimilarityExamplePickerModal';
import { SentencePanel } from './components/SentencePanel';
import { WordGenerationPanel } from './components/WordGenerationPanel';
import { ExampleEditorProvider } from './ExampleEditorProvider';
import { useExampleEditor } from './ExampleEditorContext';

export function ExampleEditorPage() {
  return (
    <ExampleEditorProvider>
      <ExampleEditorContent />
    </ExampleEditorProvider>
  );
}

function ExampleEditorContent() {
  const { autoFlow } = useExampleEditor();

  return (
    <div className="mx-auto flex min-h-full w-full max-w-[1800px] flex-col gap-4 px-4 py-4 sm:px-6 lg:px-8 lg:py-6">
      <header className="rounded-lg border border-[#0f0f0f] bg-[#0f0f0f] px-5 py-5 text-white shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-black uppercase text-white/50">Onigiri Neo</p>
            <h1 className="mt-1 text-2xl font-black leading-tight sm:text-3xl">
              Example 편집기
            </h1>
          </div>
          <button
            type="button"
            disabled={autoFlow.cannotRun}
            className={[
              'group inline-flex min-h-14 w-full items-center justify-center gap-3 rounded-lg border-2 px-5 py-3 text-left shadow-[0_16px_34px_rgba(209,67,67,0.35)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40 sm:w-auto',
              autoFlow.cannotRun
                ? 'border-white/15 bg-white/10 text-white/45 shadow-none'
                : 'border-[#ffdddd] bg-[var(--app-accent)] text-white hover:bg-[var(--app-accent-strong)]',
            ].join(' ')}
            onClick={() => {
              void autoFlow.run();
            }}
          >
            <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white text-[var(--app-accent)]">
              <Sparkles className="h-5 w-5" aria-hidden="true" />
            </span>
            <span className="grid min-w-0 gap-0.5">
              <span className="text-base font-black leading-tight">
                {autoFlow.isRunning ? '자동 생성 중' : '한 번에 자동 생성'}
              </span>
              <span className="text-xs font-black leading-tight text-white/80">
                {autoFlow.isRunning
                  ? autoFlow.step ?? '순서대로 실행 중'
                  : '문장 · 단어 · 번역 · 프롬프트 · 형태소 · 오디오'}
              </span>
            </span>
          </button>
        </div>
        {autoFlow.error ? (
          <p className="mt-3 text-xs font-black text-[#ffb3b3]">
            {autoFlow.error}
          </p>
        ) : null}
      </header>

      <div className="grid gap-4 xl:grid-cols-[minmax(420px,1.2fr)_minmax(0,1fr)]">
        <div className="grid min-w-0 gap-4">
          <SentencePanel />
          <WordGenerationPanel />
        </div>
        <div className="grid min-w-0 gap-4">
          <AudioPanel />
          <ImagePanel />
        </div>
      </div>
      <ExampleSaveConfirmModal />
      <LowExampleCountWordPickerModal />
      <LowSimilarityExamplePickerModal />
    </div>
  );
}
