import { useCallback, useEffect, useMemo, useState } from 'react';
import { dbTables } from '../../../api/api';
import type { GetListRequest, ImageRecord } from '../../../api/types';
import type {
  ImageExplorerSortDirection,
  ImageExplorerSortField,
} from '../types';

const PAGE_SIZE = 24;

export function useImageList() {
  const [items, setItems] = useState<ImageRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState('');
  const [searchText, setSearchText] = useState('');
  const [sortField, setSortField] = useState<ImageExplorerSortField>('id');
  const [sortDirection, setSortDirection] =
    useState<ImageExplorerSortDirection>('desc');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / PAGE_SIZE)),
    [total],
  );

  const loadImages = useCallback(async () => {
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
      const response = await dbTables.Image.listRows(request);
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
          : '이미지 목록을 불러오지 못했습니다.',
      );
      setItems([]);
      setTotal(0);
    } finally {
      setIsLoading(false);
    }
  }, [page, searchText, sortDirection, sortField]);

  useEffect(() => {
    queueMicrotask(() => {
      void loadImages();
    });
  }, [loadImages]);

  const submitSearch = () => {
    setPage(1);
    setSearchText(searchInput.trim());
  };

  const resetSearch = () => {
    setPage(1);
    setSearchInput('');
    setSearchText('');
  };

  const changeSortField = (field: ImageExplorerSortField) => {
    setPage(1);
    setSortField(field);
  };

  const toggleSortDirection = () => {
    setPage(1);
    setSortDirection((currentDirection) =>
      currentDirection === 'asc' ? 'desc' : 'asc',
    );
  };

  const updateListItem = (updatedImage: ImageRecord) => {
    if (updatedImage.id == null) {
      return;
    }

    setItems((currentItems) =>
      currentItems.map((image) =>
        image.id === updatedImage.id ? { ...image, ...updatedImage } : image,
      ),
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
    setPage,
    setSearchInput,
    submitSearch,
    resetSearch,
    changeSortField,
    toggleSortDirection,
    refresh: loadImages,
    updateListItem,
  };
}
