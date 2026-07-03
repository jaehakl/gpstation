import { ImageIcon, Save, Search } from 'lucide-react';
import { SDXL_IMAGE_ASPECT_RATIO } from '../api/constants';

export type ImagePanelState = {
  isGeneratingImage: boolean;
  isRecommending: boolean;
  isSaving: boolean;
  imageGenerationError: string | null;
  recommendationError: string | null;
  saveError: string | null;
  saveMessage: string | null;
  previewSrc: string | null;
  previewAlt: string | undefined;
  currentPrompt: string;
  currentNegativePrompt: string;
  currentScoreLabel: string | null;
  cannotGenerateImage: boolean;
  cannotRecommendImage: boolean;
  canSave: boolean;
  recommend: () => Promise<void>;
  generateImage: () => Promise<void>;
  save: () => Promise<void>;
};

export type ImagePanelProps = {
  image: ImagePanelState;
};

export function ImagePanel({ image }: ImagePanelProps) {
  return (
    <section className="rounded-lg border border-[var(--app-border)] bg-[var(--app-panel)] p-4 shadow-sm">
      <div className="flex flex-col gap-2 border-b border-[var(--app-border)] pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-black uppercase text-[var(--app-accent)]">Images</p>
          <h2 className="mt-1 text-xl font-black text-[var(--app-text)]">이미지 선택/생성</h2>
        </div>
      </div>

      <div className="mt-4 grid gap-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm font-black text-[var(--app-text)]">SDXL 이미지</p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              disabled={image.cannotRecommendImage}
              className={[
                'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                image.cannotRecommendImage
                  ? 'border-[var(--app-border)] bg-[#f3f3f3] text-[var(--app-muted)]'
                  : 'border-[#2e2d2d] bg-white text-[var(--app-text)] hover:bg-[#f3f3f3]',
              ].join(' ')}
              onClick={() => {
                void image.recommend();
              }}
            >
              <Search className="h-4 w-4" aria-hidden="true" />
              {image.isRecommending ? '추천 중' : '이미지 추천'}
            </button>
            <button
              type="button"
              disabled={image.cannotGenerateImage}
              className={[
                'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                image.cannotGenerateImage
                  ? 'border-[var(--app-border)] bg-[#f3f3f3] text-[var(--app-muted)]'
                  : 'border-[#2e2d2d] bg-white text-[var(--app-text)] hover:bg-[#f3f3f3]',
              ].join(' ')}
              onClick={() => {
                void image.generateImage();
              }}
            >
              <ImageIcon className="h-4 w-4" aria-hidden="true" />
              {image.isGeneratingImage ? '이미지 생성 중' : 'SDXL 이미지 생성'}
            </button>
            <button
              type="button"
              disabled={!image.canSave}
              className={[
                'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                image.canSave
                  ? 'border-[#b02c2c] bg-[var(--app-accent)] text-white hover:bg-[var(--app-accent-strong)]'
                  : 'border-[var(--app-border)] bg-[#d1d1d1] text-white opacity-70',
              ].join(' ')}
              onClick={() => {
                void image.save();
              }}
            >
              <Save className="h-4 w-4" aria-hidden="true" />
              {image.isSaving ? '저장 중' : '이미지 저장'}
            </button>
          </div>
        </div>
        {image.recommendationError ? (
          <p className="text-xs font-black text-[var(--app-accent)]">
            {image.recommendationError}
          </p>
        ) : null}
        {image.imageGenerationError ? (
          <p className="text-xs font-black text-[var(--app-accent)]">
            {image.imageGenerationError}
          </p>
        ) : null}
        {image.saveError ? (
          <p className="text-xs font-black text-[var(--app-accent)]">
            {image.saveError}
          </p>
        ) : null}
        {image.saveMessage ? (
          <p className="text-xs font-black text-[#257a38]">
            {image.saveMessage}
          </p>
        ) : null}

        <div className="grid gap-3 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <div>
            <p className="mb-1.5 text-sm font-black text-[var(--app-text)]">현재 선택된 이미지</p>
            <div
              className="flex min-h-[220px] items-center justify-center overflow-hidden rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa]"
              style={{ aspectRatio: SDXL_IMAGE_ASPECT_RATIO }}
            >
              {image.previewSrc ? (
                <img
                  src={image.previewSrc}
                  alt={image.previewAlt ?? '현재 선택된 이미지'}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="grid justify-items-center gap-2 text-center text-sm font-bold text-[var(--app-muted)]">
                  <ImageIcon className="h-8 w-8" aria-hidden="true" />
                  선택된 이미지가 없습니다.
                </div>
              )}
            </div>
          </div>

          <div>
            <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-black text-[var(--app-text)]">현재 이미지 프롬프트</p>
              {image.currentScoreLabel ? (
                <span className="rounded-lg border border-[#2e2d2d] bg-[#f3f3f3] px-2 py-1 text-xs font-black text-[var(--app-text)]">
                  similarity {image.currentScoreLabel}
                </span>
              ) : null}
            </div>
            <div className="grid min-h-[220px] content-start gap-4 rounded-lg border border-[var(--app-border)] bg-white p-4">
              <div>
                <p className="text-xs font-black uppercase text-[var(--app-muted)]">Positive</p>
                <p className="mt-1 whitespace-pre-wrap break-words text-sm font-semibold leading-6 text-[var(--app-text)]">
                  {image.currentPrompt || '-'}
                </p>
              </div>
              <div>
                <p className="text-xs font-black uppercase text-[var(--app-muted)]">Negative</p>
                <p className="mt-1 whitespace-pre-wrap break-words text-sm font-semibold leading-6 text-[var(--app-text)]">
                  {image.currentNegativePrompt || '-'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
