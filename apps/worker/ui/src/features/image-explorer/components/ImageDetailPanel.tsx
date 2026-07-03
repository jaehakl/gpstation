import { ImageIcon, Save, Sparkles, Trash2 } from 'lucide-react';
import { SDXL_IMAGE_ASPECT_RATIO } from '../../../api/constants';
import { useImageExplorer } from '../ImageExplorerContext';
import { SimilarPanel } from './SimilarPanel';

const textareaClass =
  'min-h-28 w-full rounded-lg border border-[var(--app-border)] bg-white px-3 py-2 text-sm font-semibold text-[var(--app-text)] outline-none transition placeholder:text-[#9a9a9a] focus:border-[var(--app-accent)] focus:ring-2 focus:ring-[var(--app-focus)]';

export function ImageDetailPanel() {
  const { detail, selectedImage, session } = useImageExplorer();

  if (!selectedImage) {
    return (
      <section className="flex min-h-[620px] items-center justify-center rounded-lg border border-dashed border-[var(--app-border)] bg-[var(--app-panel)] px-6 py-10 text-center shadow-sm">
        <div>
          <p className="text-xs font-black uppercase text-[var(--app-accent)]">Detail</p>
          <h2 className="mt-2 text-2xl font-black text-[var(--app-text)]">
            이미지를 선택하세요
          </h2>
          <p className="mt-2 text-sm font-bold text-[var(--app-muted)]">
            왼쪽 탐색기에서 이미지를 선택하면 상세 데이터가 표시됩니다.
          </p>
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
            <p className="text-xs font-black uppercase text-[var(--app-accent)]">Image</p>
            <h2 className="mt-1 truncate text-xl font-black text-[var(--app-text)]">
              Image #{selectedImage.id ?? '-'}
            </h2>
            <p className="mt-1 truncate text-xs font-bold text-[var(--app-muted)]">
              {selectedImage.updated_at
                ? `updated ${new Date(selectedImage.updated_at).toLocaleString('ko-KR')}`
                : 'updated -'}
            </p>
          </div>
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
              if (window.confirm('이 이미지를 삭제할까요?')) {
                void detail.deleteImage();
              }
            }}
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            {detail.isDeleting ? '삭제 중' : '삭제'}
          </button>
        </div>

        <div className="mt-4 grid gap-4">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <div>
              <p className="mb-1.5 text-sm font-black text-[var(--app-text)]">
                이미지
              </p>
              <div
                className="flex min-h-[260px] items-center justify-center overflow-hidden rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa]"
                style={{ aspectRatio: SDXL_IMAGE_ASPECT_RATIO }}
              >
                {detail.previewSrc ? (
                  <img
                    src={detail.previewSrc}
                    alt={detail.previewAlt}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="grid justify-items-center gap-2 text-center text-sm font-bold text-[var(--app-muted)]">
                    <ImageIcon className="h-8 w-8" aria-hidden="true" />
                    이미지 파일이 없습니다.
                  </div>
                )}
              </div>
            </div>

            <div className="grid content-start gap-4 text-sm font-black text-[var(--app-text)]">
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
                  onChange={(event) =>
                    detail.setField('negativePrompt', event.target.value)
                  }
                />
              </label>
            </div>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              {detail.isDirty
              && detail.saveDisabledReason === '마지막 이미지 생성 후 prompt가 변경되었습니다.' ? (
                <p className="text-xs font-black text-[var(--app-muted)]">
                  prompt 변경 후 이미지를 다시 생성해야 저장할 수 있습니다.
                </p>
              ) : null}
              {!session.isAdmin ? (
                <p className="text-xs font-bold text-[var(--app-muted)]">
                  admin 권한이 있어야 이미지를 저장할 수 있습니다.
                </p>
              ) : null}
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                disabled={!detail.canGenerate}
                className={[
                  'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-4 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                  detail.canGenerate
                    ? 'border-[#2e2d2d] bg-white text-[var(--app-text)] hover:bg-[#f3f3f3]'
                    : 'border-[var(--app-border)] bg-[#f3f3f3] text-[var(--app-muted)] opacity-70',
                ].join(' ')}
                onClick={() => {
                  void detail.generateImage();
                }}
              >
                <Sparkles className="h-4 w-4" aria-hidden="true" />
                {detail.isGenerating ? '생성 중' : '이미지 생성'}
              </button>
              <button
                type="button"
                disabled={!detail.canSave}
                title={detail.saveDisabledReason ?? '저장'}
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
                {detail.isSaving ? '저장 중' : '저장'}
              </button>
            </div>
          </div>

          {detail.saveDisabledReason && !detail.canSave ? (
            <p className="text-xs font-black text-[var(--app-muted)]">
              {detail.saveDisabledReason}
            </p>
          ) : null}
          {detail.generationError ? (
            <p className="text-xs font-black text-[var(--app-accent)]">
              {detail.generationError}
            </p>
          ) : null}
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
            <p className="text-xs font-black text-[#167347]">
              {detail.deleteMessage}
            </p>
          ) : null}
        </div>
      </section>

      <SimilarPanel />
    </div>
  );
}
