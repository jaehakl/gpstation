import { ImageIcon, RefreshCw } from 'lucide-react';
import { SDXL_IMAGE_ASPECT_RATIO } from '../../../api/constants';
import { useImageExplorer } from '../ImageExplorerContext';

export function SimilarPanel() {
  const { selectedImage, selectImage, similar } = useImageExplorer();

  return (
    <section className="rounded-lg border border-[var(--app-border)] bg-[var(--app-panel)] p-4 shadow-sm">
      <div className="flex flex-col gap-2 border-b border-[var(--app-border)] pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-black uppercase text-[var(--app-accent)]">Similar</p>
          <h2 className="mt-1 text-xl font-black text-[var(--app-text)]">유사 항목</h2>
        </div>
        <button
          type="button"
          disabled={!selectedImage || similar.isLoading}
          title="새로고침"
          className={[
            'inline-flex h-10 w-10 items-center justify-center rounded-lg border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
            selectedImage && !similar.isLoading
              ? 'border-[#2e2d2d] bg-white text-[var(--app-text)] hover:bg-[#f3f3f3]'
              : 'border-[var(--app-border)] bg-[#f3f3f3] text-[var(--app-muted)] opacity-70',
          ].join(' ')}
          onClick={() => {
            void similar.refresh();
          }}
        >
          <RefreshCw
            className={[
              'h-4 w-4',
              similar.isLoading ? 'animate-spin' : '',
            ].join(' ')}
            aria-hidden="true"
          />
        </button>
      </div>

      <div className="mt-4 grid gap-5">
        {similar.error ? (
          <p className="text-sm font-black text-[var(--app-accent)]">
            {similar.error}
          </p>
        ) : null}
        {similar.isLoading ? (
          <p className="text-sm font-bold text-[var(--app-muted)]">
            유사 항목을 불러오는 중입니다.
          </p>
        ) : null}

        <div>
          <p className="mb-2 text-sm font-black text-[var(--app-text)]">
            Similar Images
          </p>
          {similar.images.length === 0 && !similar.isLoading ? (
            <div className="flex h-28 items-center justify-center rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa] text-sm font-bold text-[var(--app-muted)]">
              유사 이미지가 없습니다.
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-5 2xl:grid-cols-6">
              {similar.images.map((image, index) => (
                <button
                  key={image.id ?? image.object_key ?? image.prompt ?? `similar-image-${index}`}
                  type="button"
                  className="flex items-center justify-center overflow-hidden rounded-lg border border-[var(--app-border)] bg-[#fafafa] shadow-sm transition hover:border-[#606060] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                  style={{ aspectRatio: SDXL_IMAGE_ASPECT_RATIO }}
                  title={image.id != null ? `image-${image.id}` : 'image'}
                  onClick={() => selectImage(image)}
                >
                  {image.object_key ? (
                    <img
                      src={image.object_key}
                      alt=""
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <ImageIcon
                      className="h-7 w-7 text-[var(--app-muted)]"
                      aria-hidden="true"
                    />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        <div>
          <p className="mb-2 text-sm font-black text-[var(--app-text)]">
            Similar Examples
          </p>
          {similar.examples.length === 0 && !similar.isLoading ? (
            <div className="flex h-28 items-center justify-center rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa] text-sm font-bold text-[var(--app-muted)]">
              유사 예문이 없습니다.
            </div>
          ) : (
            <div className="grid gap-3">
              {similar.examples.map((example, index) => (
                <article
                  key={example.id ?? `${example.jp_text}-${example.kr_text}-${index}`}
                  className="rounded-lg border border-[var(--app-border)] bg-white p-3"
                >
                  <p className="whitespace-pre-wrap break-words text-sm font-black leading-6 text-[var(--app-text)]">
                    {example.jp_text}
                  </p>
                  <p className="mt-2 whitespace-pre-wrap break-words text-sm font-semibold leading-6 text-[var(--app-muted)]">
                    {example.kr_text}
                  </p>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
