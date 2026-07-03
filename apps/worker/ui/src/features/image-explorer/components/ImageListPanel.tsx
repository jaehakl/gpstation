import {
  ArrowDown,
  ArrowUp,
  ImageIcon,
  RotateCcw,
  Search,
} from 'lucide-react';
import type { FormEvent } from 'react';
import { SDXL_IMAGE_ASPECT_RATIO } from '../../../api/constants';
import { useImageExplorer } from '../ImageExplorerContext';
import type { ImageExplorerSortField } from '../types';

const sortOptions: Array<{ value: ImageExplorerSortField; label: string }> = [
  { value: 'id', label: 'ID' },
  { value: 'created_at', label: '생성일' },
  { value: 'updated_at', label: '수정일' },
  { value: 'prompt', label: 'Prompt' },
  { value: 'negative_prompt', label: 'Negative prompt' },
];

export function ImageListPanel() {
  const { list, selectedImage, selectImage } = useImageExplorer();
  const firstItemNumber = list.total === 0 ? 0 : (list.page - 1) * list.pageSize + 1;
  const lastItemNumber = Math.min(list.page * list.pageSize, list.total);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    list.submitSearch();
  };

  return (
    <section className="flex min-h-[620px] min-w-0 flex-col rounded-lg border border-[var(--app-border)] bg-[var(--app-panel)] shadow-sm">
      <div className="border-b border-[var(--app-border)] p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between xl:flex-col xl:items-stretch 2xl:flex-row 2xl:items-end">
          <div className="min-w-0">
            <p className="text-xs font-black uppercase text-[var(--app-accent)]">Images</p>
            <h2 className="mt-1 text-xl font-black text-[var(--app-text)]">이미지 탐색기</h2>
          </div>
          <p className="text-xs font-black text-[var(--app-muted)]">
            {firstItemNumber}-{lastItemNumber} / {list.total}
          </p>
        </div>

        <form className="mt-4 flex gap-2" onSubmit={handleSubmit}>
          <input
            value={list.searchInput}
            placeholder="prompt 검색"
            className="h-10 min-w-0 flex-1 rounded-lg border border-[var(--app-border)] bg-white px-3 text-sm font-semibold outline-none transition placeholder:text-[#9a9a9a] focus:border-[var(--app-accent)] focus:ring-2 focus:ring-[var(--app-focus)]"
            onChange={(event) => list.setSearchInput(event.target.value)}
          />
          <button
            type="submit"
            title="검색"
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[#2e2d2d] bg-white transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
          >
            <Search className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            title="초기화"
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[var(--app-border)] bg-white transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            onClick={list.resetSearch}
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
          </button>
        </form>

        <div className="mt-3 flex min-w-0 gap-2">
          <div className="flex min-w-0 gap-2">
            <select
              value={list.sortField}
              className="h-10 min-w-0 flex-1 rounded-lg border border-[var(--app-border)] bg-white px-3 text-sm font-black text-[var(--app-text)] outline-none transition focus:border-[var(--app-accent)] focus:ring-2 focus:ring-[var(--app-focus)]"
              aria-label="정렬 기준"
              onChange={(event) =>
                list.changeSortField(event.target.value as ImageExplorerSortField)
              }
            >
              {sortOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              title={list.sortDirection === 'asc' ? '오름차순' : '내림차순'}
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[var(--app-border)] bg-white transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
              onClick={list.toggleSortDirection}
            >
              {list.sortDirection === 'asc' ? (
                <ArrowUp className="h-4 w-4" aria-hidden="true" />
              ) : (
                <ArrowDown className="h-4 w-4" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>

        {list.searchText ? (
          <p className="mt-2 truncate text-xs font-bold text-[var(--app-muted)]">
            검색어: {list.searchText}
          </p>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {list.isLoading ? (
          <div className="flex h-48 items-center justify-center text-sm font-bold text-[var(--app-muted)]">
            이미지를 불러오는 중입니다.
          </div>
        ) : list.error ? (
          <div className="flex h-48 items-center justify-center px-4 text-center text-sm font-black text-[var(--app-accent)]">
            {list.error}
          </div>
        ) : list.items.length === 0 ? (
          <div className="flex h-48 items-center justify-center text-sm font-bold text-[var(--app-muted)]">
            이미지가 없습니다.
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-3 2xl:grid-cols-4">
            {list.items.map((image, index) => {
              const imageId = image.id;
              const isSelected = imageId != null && imageId === selectedImage?.id;

              return (
                <div
                  key={image.id ?? image.object_key ?? image.prompt ?? `image-${index}`}
                  style={{ aspectRatio: SDXL_IMAGE_ASPECT_RATIO }}
                  className={[
                    'group relative overflow-hidden rounded-lg border bg-[#fafafa] shadow-sm transition',
                    isSelected
                      ? 'border-[var(--app-accent)] ring-2 ring-[var(--app-focus)]'
                      : 'border-[var(--app-border)] hover:border-[#606060]',
                  ].join(' ')}
                >
                  <button
                    type="button"
                    className="flex h-full w-full items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--app-focus)]"
                    title={imageId != null ? `image-${imageId}` : 'image'}
                    onClick={() => selectImage(image)}
                  >
                    {image.object_key ? (
                      <img
                        src={image.object_key}
                        alt=""
                        className="h-full w-full object-cover transition duration-200 group-hover:scale-[1.03]"
                      />
                    ) : (
                      <ImageIcon
                        className="h-8 w-8 text-[var(--app-muted)]"
                        aria-hidden="true"
                      />
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-3 border-t border-[var(--app-border)] p-4 sm:flex-row sm:items-center sm:justify-between">
        <button
          type="button"
          disabled={list.page <= 1}
          className="inline-flex h-10 items-center justify-center rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-black transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:border-[var(--app-border)] disabled:text-[var(--app-muted)] disabled:opacity-60"
          onClick={() => list.setPage(Math.max(1, list.page - 1))}
        >
          이전
        </button>
        <div className="text-center text-sm font-black text-[var(--app-text)]">
          {list.page} / {list.totalPages}
        </div>
        <button
          type="button"
          disabled={list.page >= list.totalPages}
          className="inline-flex h-10 items-center justify-center rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-black transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:border-[var(--app-border)] disabled:text-[var(--app-muted)] disabled:opacity-60"
          onClick={() => list.setPage(Math.min(list.totalPages, list.page + 1))}
        >
          다음
        </button>
      </div>
    </section>
  );
}
