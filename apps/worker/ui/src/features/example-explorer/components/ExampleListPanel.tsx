import { ArrowDown, ArrowUp, ArrowUpDown, RefreshCw, RotateCcw, Search } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { useExampleExplorer } from '../ExampleExplorerContext';
import type { ExampleExplorerSortField } from '../types';
import { ExampleJpWordsSyncModal } from './ExampleJpWordsSyncModal';

const sortableColumns: Array<{
  field: ExampleExplorerSortField;
  label: string;
  className?: string;
}> = [
  { field: 'id', label: 'ID', className: 'w-12 sm:w-14' },
  { field: 'jp_text', label: '일본어' },
  { field: 'similar_prompt_image_score', label: 'Image', className: 'w-14 text-right sm:w-16' },
  { field: 'similar_context_text_example_score', label: 'Context', className: 'hidden w-16 text-right md:table-cell' },
  { field: 'similar_text_context_example_score', label: 'Text', className: 'hidden w-16 text-right md:table-cell' },
  { field: 'jp_words', label: 'Words', className: 'w-14 text-right sm:w-16' },
  { field: 'audios', label: 'Audio', className: 'w-14 text-right sm:w-16' },
];
const columnCount = sortableColumns.length;

function formatSimilarityScore(score?: number | null) {
  return typeof score === 'number' ? `${(score * 100).toFixed(1)}%` : '-';
}

function SortIcon({ field }: { field: ExampleExplorerSortField }) {
  const { list } = useExampleExplorer();

  if (list.sortField !== field) {
    return <ArrowUpDown className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />;
  }

  return list.sortDirection === 'asc'
    ? <ArrowUp className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
    : <ArrowDown className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />;
}

export function ExampleListPanel() {
  const { list, selectedExample, selectExample, session } = useExampleExplorer();
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false);
  const firstItemNumber = list.total === 0 ? 0 : (list.page - 1) * list.pageSize + 1;
  const lastItemNumber = Math.min(list.page * list.pageSize, list.total);
  const canSyncJpWords = session.authReady && session.isAdmin && !list.isSyncingJpWords;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    list.submitSearch();
  };

  return (
    <>
      <section className="flex min-h-[520px] min-w-0 flex-col rounded-lg border border-[var(--app-border)] bg-[var(--app-panel)] shadow-sm">
      <div className="border-b border-[var(--app-border)] p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between xl:flex-col xl:items-stretch 2xl:flex-row 2xl:items-end">
          <div className="min-w-0">
            <p className="text-xs font-black uppercase text-[var(--app-accent)]">Examples</p>
            <h2 className="mt-1 text-xl font-black text-[var(--app-text)]">예문 목록</h2>
          </div>
          <div className="flex flex-col gap-2 sm:items-end">
            <p className="text-xs font-black text-[var(--app-muted)]">
              {firstItemNumber}-{lastItemNumber} / {list.total}
            </p>
            <button
              type="button"
              disabled={!canSyncJpWords}
              title="JpWords 동기화"
              className={[
                'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                canSyncJpWords
                  ? 'border-[#2e2d2d] bg-white text-[var(--app-text)] hover:bg-[#f3f3f3]'
                  : 'cursor-not-allowed border-[var(--app-border)] bg-[#f3f3f3] text-[var(--app-muted)] opacity-70',
              ].join(' ')}
              onClick={() => {
                list.resetSyncJpWordsStatus();
                setIsSyncModalOpen(true);
              }}
            >
              <RefreshCw
                className={[
                  'h-4 w-4',
                  list.isSyncingJpWords ? 'animate-spin' : '',
                ].join(' ')}
                aria-hidden="true"
              />
              {list.isSyncingJpWords ? '동기화 중' : 'JpWords 동기화'}
            </button>
          </div>
        </div>

        <form className="mt-4 flex gap-2" onSubmit={handleSubmit}>
          <input
            value={list.searchInput}
            placeholder="일본어 또는 한국어 검색"
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

        {list.searchText ? (
          <p className="mt-2 truncate text-xs font-bold text-[var(--app-muted)]">
            검색어: {list.searchText}
          </p>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
        <table className="w-full table-fixed border-separate border-spacing-0 text-left">
          <thead className="sticky top-0 z-10 bg-[#f7f7f7]">
            <tr>
              {sortableColumns.map((column) => (
                <th
                  key={column.field}
                  className={[
                    'overflow-hidden border-b border-[var(--app-border)] px-1.5 py-2 text-xs font-black uppercase text-[var(--app-muted)] sm:px-2',
                    column.className ?? '',
                  ].join(' ')}
                >
                  <button
                    type="button"
                    className="inline-flex max-w-full items-center gap-1 rounded-md px-0.5 py-1 transition hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                    onClick={() => list.toggleSort(column.field)}
                  >
                    <span className="min-w-0 truncate">{column.label}</span>
                    <SortIcon field={column.field} />
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {list.isLoading ? (
              <tr>
                <td
                  colSpan={columnCount}
                  className="h-44 border-b border-[var(--app-border)] text-center text-sm font-bold text-[var(--app-muted)]"
                >
                  예문을 불러오는 중입니다.
                </td>
              </tr>
            ) : list.error ? (
              <tr>
                <td
                  colSpan={columnCount}
                  className="h-44 border-b border-[var(--app-border)] px-4 text-center text-sm font-black text-[var(--app-accent)]"
                >
                  {list.error}
                </td>
              </tr>
            ) : list.items.length === 0 ? (
              <tr>
                <td
                  colSpan={columnCount}
                  className="h-44 border-b border-[var(--app-border)] text-center text-sm font-bold text-[var(--app-muted)]"
                >
                  예문이 없습니다.
                </td>
              </tr>
            ) : (
              list.items.map((example) => {
                const isSelected = example.id != null && example.id === selectedExample?.id;

                return (
                  <tr
                    key={example.id ?? `${example.jp_text}-${example.kr_text}`}
                    className={[
                      'group cursor-pointer transition',
                      isSelected ? 'bg-[var(--app-accent-soft)]' : 'hover:bg-[#fafafa]',
                    ].join(' ')}
                    onClick={() => selectExample(example)}
                  >
                    <td className="overflow-hidden whitespace-nowrap border-b border-[var(--app-border)] px-2 py-3 align-top text-sm font-black text-[var(--app-text)]">
                      {example.id ?? '-'}
                    </td>
                    <td className="min-w-0 overflow-hidden border-b border-[var(--app-border)] px-2 py-3 align-top sm:px-3">
                      <p className="line-clamp-2 break-words text-sm font-bold leading-5 text-[var(--app-text)]">
                        {example.jp_text}
                      </p>
                    </td>
                    <td className="overflow-hidden whitespace-nowrap border-b border-[var(--app-border)] px-1.5 py-3 text-right align-top text-xs font-black tabular-nums text-[var(--app-text)] sm:px-2 sm:text-sm">
                      {formatSimilarityScore(example.similar_prompt_image?.score)}
                    </td>
                    <td className="hidden overflow-hidden whitespace-nowrap border-b border-[var(--app-border)] px-2 py-3 text-right align-top text-sm font-black tabular-nums text-[var(--app-text)] md:table-cell">
                      {formatSimilarityScore(example.similar_context_text_example?.score)}
                    </td>
                    <td className="hidden overflow-hidden whitespace-nowrap border-b border-[var(--app-border)] px-2 py-3 text-right align-top text-sm font-black tabular-nums text-[var(--app-text)] md:table-cell">
                      {formatSimilarityScore(example.similar_text_context_example?.score)}
                    </td>
                    <td className="overflow-hidden whitespace-nowrap border-b border-[var(--app-border)] px-1.5 py-3 text-right align-top text-xs font-black tabular-nums text-[var(--app-text)] sm:px-2 sm:text-sm">
                      {example.jp_words?.length ?? 0}
                    </td>
                    <td className="overflow-hidden whitespace-nowrap border-b border-[var(--app-border)] px-1.5 py-3 text-right align-top text-xs font-black tabular-nums text-[var(--app-text)] sm:px-2 sm:text-sm">
                      {example.audios?.length ?? 0}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
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
      <ExampleJpWordsSyncModal
        isOpen={isSyncModalOpen}
        onClose={() => setIsSyncModalOpen(false)}
      />
    </>
  );
}
