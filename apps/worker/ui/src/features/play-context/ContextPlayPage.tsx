'use client';

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { ImageIcon, Languages, Loader2, Search, Shuffle, Trash2, X } from 'lucide-react';
import { dbTables } from '../../api/api';
import { SDXL_IMAGE_ASPECT_RATIO } from '../../api/constants';
import {
  getGuestJapaneseTextSkills,
  saveGuestJapaneseWordSkill,
} from '../../api/guestJapaneseWordSkills';
import type {
  AnalyzeJapaneseWord,
  ExampleContextPlayResponse,
  ExampleRecord,
} from '../../api/types';
import { WordHighlighter, type WordHighlighterWord } from '../../components/WordHighlighter';
import { WordInputModal, type WordInputModalValue } from '../../components/WordInputModal';
import { useAuthStore } from '../../stores/authStore';

const randomExampleRequest = {
  offset: 0,
  limit: 1,
  selected_ids: [],
  search_text: null,
  text_filter: {},
  filter: {},
  sort: null,
  random: true,
};

const pendingContextPlayRequests = new Map<string, Promise<ExampleContextPlayResponse>>();

type ContextPlayPageProps = {
  exampleId: number;
};

export function ContextPlayPage({ exampleId }: ContextPlayPageProps) {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const userId = user?.id ?? null;
  const isAdmin = user?.roles.includes('admin') ?? false;
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [data, setData] = useState<ExampleContextPlayResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isDataLoading, setIsDataLoading] = useState(false);
  const [similarExamples, setSimilarExamples] = useState<ExampleRecord[]>([]);
  const [isRandomLoading, setIsRandomLoading] = useState(false);
  const [randomError, setRandomError] = useState<string | null>(null);
  const [isDeletingExample, setIsDeletingExample] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [selectedWordId, setSelectedWordId] = useState<string | null>(null);
  const [isWordModalOpen, setIsWordModalOpen] = useState(false);
  const [analysisWords, setAnalysisWords] = useState<AnalyzeJapaneseWord[]>([]);
  const [isKrTextModalOpen, setIsKrTextModalOpen] = useState(false);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [exampleSearchInput, setExampleSearchInput] = useState('');
  const [exampleSearchText, setExampleSearchText] = useState('');
  const [exampleSearchResults, setExampleSearchResults] = useState<ExampleRecord[]>([]);
  const [isExampleSearchLoading, setIsExampleSearchLoading] = useState(false);
  const [exampleSearchError, setExampleSearchError] = useState<string | null>(null);
  const [currentAudioUrl, setCurrentAudioUrl] = useState<string | null>(null);
  const [audioPlayKey, setAudioPlayKey] = useState(0);

  const words = useMemo<WordHighlighterWord[]>(
    () =>
      analysisWords.map((word) => ({
        id: word.id,
        wordId: word.word_id,
        surface: word.surface,
        lemma: word.lemma,
        jpPron: word.jpPron,
        krMean: word.krMean,
        userWordSkill: word.userWordSkill
          ? {
              reading: word.userWordSkill.reading,
            }
          : null,
      })),
    [analysisWords],
  );
  const selectedWord = analysisWords.find((word) => word.id === selectedWordId) ?? null;
  const selectedWordCanSaveSkill = selectedWord
    ? selectedWord.word_id != null || (isAdmin && selectedWord.lemma_id != null)
    : false;
  const selectedModalWord = useMemo<WordInputModalValue | null>(
    () =>
      selectedWord
        ? {
            id: selectedWord.id,
            wordId: selectedWord.word_id,
            lemmaId: selectedWord.lemma_id,
            surface: selectedWord.surface,
            lemma: selectedWord.lemma,
            jpPron: selectedWord.jpPron,
            krMean: selectedWord.krMean,
            reading: selectedWord.userWordSkill?.reading ?? 0,
            userWordSkill: selectedWord.userWordSkill
              ? {
                  id: selectedWord.userWordSkill.id ?? null,
                  reading: selectedWord.userWordSkill.reading,
                  listening: selectedWord.userWordSkill.listening,
                  speaking: selectedWord.userWordSkill.speaking,
                }
              : null,
          }
        : null,
    [selectedWord],
  );

  const playRandomAudio = useCallback(() => {
    const urls = data?.audio_urls ?? [];
    if (urls.length === 0) {
      return;
    }

    const nextUrl = urls[Math.floor(Math.random() * urls.length)];
    setCurrentAudioUrl(nextUrl);
    setAudioPlayKey((currentKey) => currentKey + 1);
  }, [data?.audio_urls]);

  const goToRandomExample = useCallback(async () => {
    if (isRandomLoading) {
      return;
    }

    setIsRandomLoading(true);
    setRandomError(null);

    try {
      const firstResponse = await dbTables.Example.listRows(randomExampleRequest);
      let nextExample = firstResponse.items[0] ?? null;

      if (nextExample?.id === exampleId) {
        const retryResponse = await dbTables.Example.listRows(randomExampleRequest);
        nextExample = retryResponse.items[0] ?? nextExample;
      }

      if (!nextExample?.id) {
        throw new Error('이동할 예문을 찾지 못했습니다.');
      }

      router.push(`/context-play/${nextExample.id}`);
    } catch (error) {
      setRandomError(error instanceof Error ? error.message : '다른 예문을 불러오지 못했습니다.');
    } finally {
      setIsRandomLoading(false);
    }
  }, [exampleId, isRandomLoading, router]);

  const submitExampleSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (isExampleSearchLoading) {
      return;
    }

    const query = exampleSearchInput.trim();
    if (!query) {
      setExampleSearchText('');
      setExampleSearchResults([]);
      setExampleSearchError(null);
      return;
    }

    setIsExampleSearchLoading(true);
    setExampleSearchError(null);
    setExampleSearchText(query);

    try {
      const response = await dbTables.Example.listRows({
        offset: 0,
        limit: 20,
        selected_ids: [],
        search_text: query,
        text_filter: {},
        filter: {},
        sort: null,
      });
      setExampleSearchResults(response.items);
    } catch (error) {
      setExampleSearchError(
        error instanceof Error ? error.message : '예문을 검색하지 못했습니다.',
      );
      setExampleSearchResults([]);
    } finally {
      setIsExampleSearchLoading(false);
    }
  };

  useEffect(() => {
    let ignore = false;

    setIsKrTextModalOpen(false);
    setSelectedWordId(null);
    setIsWordModalOpen(false);
    setCurrentAudioUrl(null);
    setAudioPlayKey(0);
    setRandomError(null);
    setDeleteError(null);
    setData(null);
    setLoadError(null);
    setAnalysisWords([]);
    setSimilarExamples([]);

    if (!authReady) {
      setIsDataLoading(false);
      return;
    }

    const guestSkills = userId ? undefined : getGuestJapaneseTextSkills();
    const requestKey = userId
      ? `user:${userId}:example:${exampleId}`
      : `guest:${exampleId}:skills:${JSON.stringify(guestSkills)}`;
    setIsDataLoading(true);

    const loadContextPlay = async () => {
      try {
        let requestPromise = pendingContextPlayRequests.get(requestKey);
        if (!requestPromise) {
          requestPromise = dbTables.Example.contextPlay(exampleId, guestSkills);
          pendingContextPlayRequests.set(requestKey, requestPromise);
          const pendingRequest = requestPromise;
          void pendingRequest.catch(() => undefined).then(() => {
            if (pendingContextPlayRequests.get(requestKey) === pendingRequest) {
              pendingContextPlayRequests.delete(requestKey);
            }
          });
        }

        const response = await requestPromise;
        if (!ignore) {
          const shuffledExamples = [...response.similar_examples];
          for (let index = shuffledExamples.length - 1; index > 0; index -= 1) {
            const randomIndex = Math.floor(Math.random() * (index + 1));
            [shuffledExamples[index], shuffledExamples[randomIndex]] = [
              shuffledExamples[randomIndex],
              shuffledExamples[index],
            ];
          }
          setData(response);
          setAnalysisWords(response.analysis.words);
          setSimilarExamples(shuffledExamples);

          if (response.audio_urls.length > 0) {
            const nextUrl = response.audio_urls[
              Math.floor(Math.random() * response.audio_urls.length)
            ];
            setCurrentAudioUrl(nextUrl);
            setAudioPlayKey((currentKey) => currentKey + 1);
          }
        }
      } catch (error) {
        if (!ignore) {
          setLoadError(
            error instanceof Error ? error.message : '컨텍스트 플레이 데이터를 불러오지 못했습니다.',
          );
        }
      } finally {
        if (!ignore) {
          setIsDataLoading(false);
        }
      }
    };

    void loadContextPlay();

    return () => {
      ignore = true;
    };
  }, [authReady, exampleId, userId]);

  useEffect(() => {
    if (!currentAudioUrl || !audioRef.current) {
      return;
    }

    audioRef.current.load();
    audioRef.current.currentTime = 0;
    void audioRef.current.play().catch(() => {});
  }, [audioPlayKey, currentAudioUrl]);

  const submitWord = async (word: WordInputModalValue) => {
    if (!authReady) {
      throw new Error('사용자 정보를 확인 중입니다.');
    }
    if (!selectedWord) {
      throw new Error('단어를 선택해 주세요.');
    }

    const parsedReading = Number(word.reading);
    const reading = Number.isFinite(parsedReading)
      ? Math.max(0, Math.min(100, Math.round(parsedReading)))
      : 0;
    const currentSkill = selectedWord.userWordSkill;
    const originalWordId = selectedWord.word_id;
    const selectedLemmaId = selectedWord.lemma_id;
    let persistedWordId = selectedWord.word_id;
    let lemma = selectedWord.lemma;
    let krMean = selectedWord.krMean;
    const now = new Date().toISOString();

    if (isAdmin) {
      const lemmaId = selectedWord.lemma_id ?? word.lemmaId;
      if (lemmaId == null) {
        throw new Error('저장할 lemma id가 없습니다.');
      }

      const nextLemma = (word.lemma ?? selectedWord.lemma).trim();
      if (!nextLemma) {
        throw new Error('저장할 lemma가 없습니다.');
      }

      const [wordResponse] = await dbTables.JpWord.upsertRow([
        {
          ...(persistedWordId ? { id: persistedWordId } : {}),
          lemma_id: lemmaId,
          lemma: nextLemma,
          kr_mean: word.krMean,
        },
      ]);
      persistedWordId = wordResponse?.id ?? persistedWordId;
      if (persistedWordId == null) {
        throw new Error('단어 저장 응답에 ID가 없습니다.');
      }
      lemma = nextLemma;
      krMean = word.krMean;
    }

    if (persistedWordId == null) {
      throw new Error('숙련도를 저장할 DB 단어가 없습니다.');
    }

    let nextSkill = {
      id: currentSkill?.id ?? null,
      user_id: currentSkill?.user_id ?? user?.id ?? null,
      word_id: persistedWordId,
      reading,
      listening: currentSkill?.listening ?? 0,
      speaking: currentSkill?.speaking ?? 0,
      created_at: currentSkill?.created_at ?? null,
      updated_at: now,
    };

    if (user) {
      const [response] = await dbTables.UserJpWordSkill.upsertRow([
        {
          ...(currentSkill?.id ? { id: currentSkill.id } : {}),
          word_id: persistedWordId,
          reading,
          listening: currentSkill?.listening ?? 0,
          speaking: currentSkill?.speaking ?? 0,
        },
      ]);
      nextSkill = {
        ...nextSkill,
        id: response?.id ?? nextSkill.id,
        user_id: user.id,
      };
    } else {
      const savedSkill = saveGuestJapaneseWordSkill(persistedWordId, reading);
      nextSkill = {
        ...nextSkill,
        updated_at: savedSkill.updated_at,
      };
    }

    setAnalysisWords((currentWords) =>
      currentWords.map((currentWord) => {
        const isSameOriginalWord =
          originalWordId != null && currentWord.word_id === originalWordId;
        const isSameNewLemma =
          originalWordId == null
          && selectedLemmaId != null
          && currentWord.lemma_id === selectedLemmaId;

        if (
          currentWord.id !== selectedWord.id
          && !isSameOriginalWord
          && !isSameNewLemma
        ) {
          return currentWord;
        }

        return {
          ...currentWord,
          word_id: persistedWordId,
          lemma,
          krMean,
          userWordSkill: nextSkill,
        };
      }),
    );
  };

  const deleteCurrentExample = async () => {
    if (isDeletingExample) {
      return;
    }

    if (!authReady) {
      setDeleteError('사용자 정보를 확인 중입니다.');
      return;
    }

    if (!isAdmin) {
      setDeleteError('admin 권한이 있어야 예문을 삭제할 수 있습니다.');
      return;
    }

    const currentExampleId = data?.example.id ?? exampleId;
    if (!currentExampleId) {
      setDeleteError('삭제할 예문을 찾지 못했습니다.');
      return;
    }

    setIsDeletingExample(true);
    setDeleteError(null);
    setRandomError(null);

    try {
      await dbTables.Example.deleteRows([currentExampleId]);
      router.push('/context-play');
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : '예문을 삭제하지 못했습니다.');
      setIsDeletingExample(false);
    }
  };

  const shouldShowLoading = !authReady || isDataLoading || (!data && !loadError);
  const shouldShowError = !data && loadError;

  return (
    <div className="mx-auto flex min-h-full w-full max-w-6xl flex-col gap-4 bg-white px-4 py-4 sm:bg-transparent sm:px-6 lg:px-8 lg:py-6">
      <section className="hidden sm:block sm:rounded-lg sm:border sm:border-[#0f0f0f] sm:bg-[#0f0f0f] sm:px-5 sm:py-4 sm:text-white sm:shadow-sm">
        <p className="text-xs font-black uppercase tracking-[0.14em] text-white/50">
          Onigiri Neo
        </p>
      </section>

      {shouldShowLoading ? (
        <section className="flex min-h-[460px] items-center justify-center px-4 text-center text-sm font-bold text-[var(--app-muted)] sm:rounded-lg sm:border sm:border-dashed sm:border-[var(--app-border)] sm:bg-[var(--app-panel)]">
          <span className="inline-flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            데이터를 불러오는 중입니다.
          </span>
        </section>
      ) : shouldShowError ? (
        <section className="flex min-h-[460px] items-center justify-center px-4 text-center text-sm font-black text-[var(--app-accent)] sm:rounded-lg sm:border sm:border-dashed sm:border-[var(--app-border)] sm:bg-[var(--app-panel)]">
          {loadError ?? randomError}
        </section>
      ) : data ? (
        <>
          <section className="grid gap-4 lg:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
            <div className="sm:rounded-lg sm:border sm:border-[var(--app-border)] sm:bg-[var(--app-panel)] sm:p-4 sm:shadow-sm">
              <div className="mb-3 hidden flex-wrap items-center justify-between gap-2 sm:flex">
              </div>
              <button
                type="button"
                disabled={!data.image_url}
                className="flex w-full items-center justify-center overflow-hidden rounded-lg text-[var(--app-muted)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-default sm:border sm:border-dashed sm:border-[var(--app-border)] sm:bg-[#fafafa]"
                style={{ aspectRatio: SDXL_IMAGE_ASPECT_RATIO }}
                onClick={playRandomAudio}
              >
                {data.image_url ? (
                  <img
                    src={data.image_url}
                    alt={`Example ${data.example.id ?? exampleId}`}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <span className="grid justify-items-center gap-2 text-sm font-bold text-[var(--app-muted)]">
                    <ImageIcon className="h-8 w-8" aria-hidden="true" />
                    이미지 없음
                  </span>
                )}
              </button>
              {currentAudioUrl ? (
                <audio ref={audioRef} src={currentAudioUrl} preload="auto" className="hidden" />
              ) : null}
            </div>

            <div className="grid gap-4">
              <section className="sm:rounded-lg sm:border sm:border-[var(--app-border)] sm:bg-[var(--app-panel)] sm:p-4 sm:shadow-sm">
                <div className="mb-2 hidden flex-wrap items-center justify-between gap-2 sm:flex">
                  {selectedWord ? (
                    <span className="max-w-full truncate text-xs font-black text-[var(--app-muted)]">
                      {selectedWord.lemma} / {selectedWord.krMean || '-'}
                    </span>
                  ) : null}
                </div>
                <WordHighlighter
                  words={words}
                  selectedWordId={selectedWordId}
                  emptyText="표시할 단어가 없습니다."
                  onWordSelect={(word) => {
                    setSelectedWordId(word.id);
                    setIsWordModalOpen(true);
                  }}
                />
              </section>
            </div>
          </section>

          <section className="sm:rounded-lg sm:border sm:border-[var(--app-border)] sm:bg-[var(--app-panel)] sm:p-4 sm:shadow-sm">
            {similarExamples.length === 0 ? (
              <div className="flex min-h-[112px] items-center justify-center px-4 text-center text-sm font-bold text-[var(--app-muted)] sm:rounded-lg sm:border sm:border-dashed sm:border-[var(--app-border)] sm:bg-[#fafafa]">
                선택지가 없습니다.
              </div>
            ) : (
              <div className="grid gap-2">
                {similarExamples.map((example, index) => (
                  <button
                    key={example.id ?? `${example.jp_text}-${index}`}
                    type="button"
                    disabled={!example.id}
                    className="min-h-12 rounded-lg border border-[#d1d1d1] bg-white px-4 py-3 text-left text-base font-black leading-7 text-[var(--app-text)] transition hover:border-[#2e2d2d] hover:bg-[#f7f7f7] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:opacity-60"
                    onClick={() => {
                      if (example.id) {
                        router.push(`/context-play/${example.id}`);
                      }
                    }}
                  >
                    {example.jp_text}
                  </button>
                ))}
              </div>
            )}
          </section>

          <section
            className={[
              'grid gap-3 sm:rounded-lg sm:border sm:border-[var(--app-border)] sm:bg-[var(--app-panel)] sm:p-4 sm:shadow-sm',
              isKrTextModalOpen ? 'relative z-[60]' : '',
            ].join(' ')}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2">
                <button
                  type="button"
                  disabled={!data}
                  className="inline-flex h-11 min-w-0 shrink-0 items-center justify-center gap-2 rounded-lg border border-[#d1d1d1] bg-white px-3 text-sm font-black !text-[#0f0f0f] shadow-sm transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:bg-[#d1d1d1] disabled:!text-[#555555] sm:px-4"
                  onClick={() => setIsKrTextModalOpen((isOpen) => !isOpen)}
                >
                  <Languages className="h-4 w-4 !text-[#0f0f0f]" aria-hidden="true" />
                  <span className="truncate !text-[#0f0f0f]">뜻</span>
                </button>
                <button
                  type="button"
                  aria-label="예문 검색"
                  title="예문 검색"
                  disabled={!data}
                  className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-[#d1d1d1] bg-white text-[#0f0f0f] shadow-sm transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:bg-[#d1d1d1] disabled:text-[#555555]"
                  onClick={() => setIsSearchModalOpen(true)}
                >
                  <Search className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
              <button
                type="button"
                disabled={isRandomLoading}
                className="inline-flex h-11 min-w-0 shrink-0 items-center justify-center gap-2 rounded-lg border border-[#b02c2c] bg-[var(--app-accent)] px-3 text-sm font-black !text-white shadow-sm transition hover:bg-[var(--app-accent-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:border-[#8a8a8a] disabled:bg-[#d1d1d1] disabled:!text-[#555555] sm:px-4"
                onClick={() => {
                  void goToRandomExample();
                }}
              >
                {isRandomLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin !text-current" aria-hidden="true" />
                ) : (
                  <Shuffle className="h-4 w-4 !text-current" aria-hidden="true" />
                )}
                <span className="truncate !text-current">
                  {isRandomLoading ? '이동 중' : '다른 예문'}
                </span>
              </button>
              {isAdmin ? (
                <button
                  type="button"
                  disabled={isDeletingExample}
                  className="inline-flex h-11 min-w-0 shrink-0 items-center justify-center gap-2 rounded-lg border border-[#ffd1d1] bg-white px-3 text-sm font-black text-[var(--app-accent)] shadow-sm transition hover:bg-[#fff4f4] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:border-[var(--app-border)] disabled:bg-[#f3f3f3] disabled:text-[var(--app-muted)] sm:px-4"
                  onClick={() => {
                    if (window.confirm('이 예문을 삭제할까요? 저장된 오디오와 오류 제보도 함께 삭제됩니다.')) {
                      void deleteCurrentExample();
                    }
                  }}
                >
                  {isDeletingExample ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  )}
                  <span className="truncate">{isDeletingExample ? '삭제 중' : '삭제'}</span>
                </button>
              ) : null}
            </div>
            {randomError ? (
              <p className="text-xs font-black text-[var(--app-accent)]">
                {randomError}
              </p>
            ) : null}
            {deleteError ? (
              <p className="text-xs font-black text-[var(--app-accent)]">
                {deleteError}
              </p>
            ) : null}
          </section>
        </>
      ) : null}

      <WordInputModal
        isOpen={isWordModalOpen}
        word={selectedModalWord}
        isAdmin={isAdmin}
        canSaveSkill={selectedWordCanSaveSkill}
        onClose={() => setIsWordModalOpen(false)}
        onSubmit={submitWord}
      />

      {isKrTextModalOpen && data ? (
        <>
          <div className="fixed inset-0 z-40 bg-black/45" />
          <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center px-4 py-6">
            <section
              role="dialog"
              aria-modal="true"
              aria-labelledby="context-play-kr-title"
              className="pointer-events-auto flex max-h-full w-full max-w-xl flex-col overflow-hidden rounded-lg border border-[#0f0f0f] bg-white shadow-[var(--app-shadow)]"
            >
              <header className="flex min-h-14 items-center gap-3 border-b border-[var(--app-border)] bg-[#0f0f0f] px-4 text-white">
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] font-black uppercase text-white/55">Korean</p>
                  <h2 id="context-play-kr-title" className="truncate text-lg font-black">
                    뜻
                  </h2>
                </div>
                <button
                  type="button"
                  aria-label="한국어 모달 닫기"
                  title="닫기"
                  className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/20 bg-white/10 text-sm font-black text-white transition hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                  onClick={() => setIsKrTextModalOpen(false)}
                >
                  X
                </button>
              </header>
              <div className="min-h-0 overflow-y-auto px-4 py-4">
                <p className="whitespace-pre-wrap break-words text-base font-bold leading-7 text-[var(--app-text)]">
                  {data.example.kr_text}
                </p>
              </div>
            </section>
          </div>
        </>
      ) : null}

      {isSearchModalOpen ? (
        <>
          <div className="fixed inset-0 z-40 bg-black/45" />
          <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center px-4 py-6">
            <section
              role="dialog"
              aria-modal="true"
              aria-labelledby="context-play-search-title"
              className="pointer-events-auto flex max-h-full w-full max-w-xl flex-col overflow-hidden rounded-lg border border-[#0f0f0f] bg-white shadow-[var(--app-shadow)]"
            >
              <header className="flex min-h-14 items-center gap-3 border-b border-[var(--app-border)] bg-[#0f0f0f] px-4 text-white">
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] font-black uppercase text-white/55">Search</p>
                  <h2 id="context-play-search-title" className="truncate text-lg font-black">
                    예문 검색
                  </h2>
                </div>
                <button
                  type="button"
                  aria-label="예문 검색 모달 닫기"
                  title="닫기"
                  className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/20 bg-white/10 text-white transition hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                  onClick={() => setIsSearchModalOpen(false)}
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              </header>

              <div className="min-h-0 overflow-y-auto px-4 py-4">
                <form className="flex gap-2" onSubmit={submitExampleSearch}>
                  <input
                    value={exampleSearchInput}
                    placeholder="일본어 또는 한국어 검색"
                    className="h-11 min-w-0 flex-1 rounded-lg border border-[var(--app-border)] bg-white px-3 text-sm font-semibold outline-none transition placeholder:text-[#9a9a9a] focus:border-[var(--app-accent)] focus:ring-2 focus:ring-[var(--app-focus)]"
                    onChange={(event) => setExampleSearchInput(event.target.value)}
                  />
                  <button
                    type="submit"
                    aria-label="예문 검색 실행"
                    title="검색"
                    disabled={isExampleSearchLoading}
                    className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-[#2e2d2d] bg-white text-[var(--app-text)] transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:border-[var(--app-border)] disabled:text-[var(--app-muted)] disabled:opacity-70"
                  >
                    {isExampleSearchLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Search className="h-4 w-4" aria-hidden="true" />
                    )}
                  </button>
                </form>

                {exampleSearchError ? (
                  <p className="mt-3 text-xs font-black text-[var(--app-accent)]">
                    {exampleSearchError}
                  </p>
                ) : null}

                <div className="mt-4 grid gap-2">
                  {isExampleSearchLoading ? (
                    <div className="flex min-h-[112px] items-center justify-center px-4 text-center text-sm font-bold text-[var(--app-muted)]">
                      <span className="inline-flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                        예문을 검색하는 중입니다.
                      </span>
                    </div>
                  ) : exampleSearchText && !exampleSearchError && exampleSearchResults.length === 0 ? (
                    <div className="flex min-h-[112px] items-center justify-center rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa] px-4 text-center text-sm font-bold text-[var(--app-muted)]">
                      검색 결과가 없습니다.
                    </div>
                  ) : (
                    exampleSearchResults.map((example, index) => (
                      <button
                        key={example.id ?? `${example.jp_text}-${index}`}
                        type="button"
                        disabled={!example.id}
                        className="min-h-12 rounded-lg border border-[#d1d1d1] bg-white px-4 py-3 text-left text-base font-black leading-7 text-[var(--app-text)] transition hover:border-[#2e2d2d] hover:bg-[#f7f7f7] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:opacity-60"
                        onClick={() => {
                          if (example.id) {
                            setIsSearchModalOpen(false);
                            router.push(`/context-play/${example.id}`);
                          }
                        }}
                      >
                        {example.jp_text}
                      </button>
                    ))
                  )}
                </div>
              </div>
            </section>
          </div>
        </>
      ) : null}
    </div>
  );
}
