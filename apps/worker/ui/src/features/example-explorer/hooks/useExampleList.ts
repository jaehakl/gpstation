import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { dbTables } from '../../../api/api';
import type {
  ExampleRecord,
  ExampleSortSimilarRecord,
  GetListRequest,
} from '../../../api/types';
import type {
  ExampleExplorerSortDirection,
  ExampleExplorerSortField,
} from '../types';

const PAGE_SIZE = 20;
const SYNC_BATCH_SIZE = 100;

type ExampleListSort = {
  field: ExampleExplorerSortField;
  direction: ExampleExplorerSortDirection;
};

type SyncJpWordsRange = {
  startId: number;
  endId: number;
};

export function useExampleList() {
  const [items, setItems] = useState<ExampleSortSimilarRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState('');
  const [searchText, setSearchText] = useState('');
  const [sort, setSort] = useState<ExampleListSort>({
    field: 'id',
    direction: 'desc',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSyncingJpWords, setIsSyncingJpWords] = useState(false);
  const [syncJpWordsError, setSyncJpWordsError] = useState<string | null>(null);
  const [syncJpWordsMessage, setSyncJpWordsMessage] = useState<string | null>(null);
  const [syncJpWordsBatchMessages, setSyncJpWordsBatchMessages] = useState<string[]>([]);
  const isSyncingJpWordsRef = useRef(false);
  const sortField = sort.field;
  const sortDirection = sort.direction;
  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / PAGE_SIZE)),
    [total],
  );

  const loadExamples = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const request: GetListRequest = {
        offset: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
        selected_ids: [],
        search_text: searchText.trim() || null,
        text_filter: {},
        filter: {},
        sort: [sortField, sortDirection],
      };
      const response = await dbTables.CreatorHelpers.listExampleRowsSortSimilar(request);
      const nextTotalPages = Math.max(1, Math.ceil(response.total / PAGE_SIZE));
      setItems(response.items);
      setTotal(response.total);
      if (page > nextTotalPages) {
        setPage(nextTotalPages);
      }
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : '예문 목록을 불러오지 못했습니다.',
      );
      setItems([]);
      setTotal(0);
    } finally {
      setIsLoading(false);
    }
  }, [page, searchText, sortDirection, sortField]);

  useEffect(() => {
    queueMicrotask(() => {
      void loadExamples();
    });
  }, [loadExamples]);

  const submitSearch = () => {
    setPage(1);
    setSearchText(searchInput.trim());
  };

  const resetSearch = () => {
    setPage(1);
    setSearchInput('');
    setSearchText('');
  };

  const resetSyncJpWordsStatus = () => {
    if (isSyncingJpWordsRef.current) {
      return;
    }

    setSyncJpWordsError(null);
    setSyncJpWordsMessage(null);
    setSyncJpWordsBatchMessages([]);
  };

  const syncJpWords = async (range?: SyncJpWordsRange) => {
    if (isSyncingJpWordsRef.current) {
      return;
    }

    isSyncingJpWordsRef.current = true;
    setIsSyncingJpWords(true);
    setSyncJpWordsError(null);
    setSyncJpWordsMessage(null);
    setSyncJpWordsBatchMessages([]);

    try {
      if (!range) {
        const response = await dbTables.CreatorHelpers.syncExampleJpWords();
        setSyncJpWordsMessage(
          `동기화 완료: 총 ${response.examples_checked}개 확인, ${response.examples_updated}개 예문 갱신, ${response.jp_words_added}개 단어 연결`,
        );
        setSyncJpWordsBatchMessages([
          `전체: ${response.examples_checked}개 확인, ${response.examples_updated}개 예문 갱신, ${response.jp_words_added}개 단어 연결`,
        ]);
        await loadExamples();
        return;
      }

      let nextStartId: number | null = range.startId;
      let batchNumber = 0;
      let totalChecked = 0;
      let totalUpdated = 0;
      let totalAdded = 0;

      while (nextStartId != null && nextStartId <= range.endId) {
        const response = await dbTables.CreatorHelpers.syncExampleJpWords({
          start_id: nextStartId,
          end_id: range.endId,
          limit: SYNC_BATCH_SIZE,
        });
        batchNumber += 1;
        totalChecked += response.examples_checked;
        totalUpdated += response.examples_updated;
        totalAdded += response.jp_words_added;

        setSyncJpWordsBatchMessages((currentMessages) => [
          ...currentMessages,
          `${batchNumber}차: ${response.examples_checked}개 확인, ${response.examples_updated}개 예문 갱신, ${response.jp_words_added}개 단어 연결`,
        ]);

        const nextBatchStartId = response.next_start_id ?? null;
        const hasNextBatch =
          nextBatchStartId != null
          && nextBatchStartId > nextStartId
          && nextBatchStartId <= range.endId
          && response.examples_checked > 0;
        setSyncJpWordsMessage(
          `${hasNextBatch ? '진행 중' : '동기화 완료'}: 총 ${totalChecked}개 확인, ${totalUpdated}개 예문 갱신, ${totalAdded}개 단어 연결`,
        );

        if (!hasNextBatch) {
          break;
        }
        nextStartId = nextBatchStartId;
      }

      await loadExamples();
    } catch (syncError) {
      setSyncJpWordsError(
        syncError instanceof Error
          ? syncError.message
          : 'JpWords 동기화를 실행하지 못했습니다.',
      );
    } finally {
      isSyncingJpWordsRef.current = false;
      setIsSyncingJpWords(false);
    }
  };

  const toggleSort = (field: ExampleExplorerSortField) => {
    setPage(1);
    setSort((currentSort) => {
      if (currentSort.field !== field) {
        return { field, direction: 'asc' };
      }

      return {
        field,
        direction: currentSort.direction === 'asc' ? 'desc' : 'asc',
      };
    });
  };

  const updateListItem = (updatedExample: ExampleRecord) => {
    setItems((currentItems) =>
      currentItems.map((item) => (
        item.id === updatedExample.id ? { ...item, ...updatedExample } : item
      )),
    );
  };

  return {
    items,
    total,
    page,
    pageSize: PAGE_SIZE,
    totalPages,
    searchInput,
    searchText,
    sortField,
    sortDirection,
    isLoading,
    error,
    isSyncingJpWords,
    syncJpWordsError,
    syncJpWordsMessage,
    syncJpWordsBatchMessages,
    setPage,
    setSearchInput,
    submitSearch,
    resetSearch,
    toggleSort,
    syncJpWords,
    resetSyncJpWordsStatus,
    refresh: loadExamples,
    updateListItem,
  };
}
