import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react';
import { dbTables } from '../../api/api';
import { aiFastApi, getGeneratedImageFileMetadata } from '../../api/apiAi';
import { SDXL_IMAGE_GENERATION_PARAMS } from '../../api/constants';
import type { ExampleRecord, GetListRequest } from '../../api/types';
import {
  getGuestJapaneseTextSkills,
  saveGuestJapaneseWordSkill,
} from '../../api/guestJapaneseWordSkills';
import type { WordInputModalValue } from '../../components/WordInputModal';
import { useAuthStore } from '../../stores/authStore';
import { ExampleEditorContext } from './ExampleEditorContext';
import type {
  GeneratedImagePreview,
  LowExampleCountWordCandidate,
  LowSimilarityExampleCandidate,
  PendingExampleSave,
  RecommendedImage,
} from './ExampleEditorContext';
import {
  fetchJapaneseWordKoreanMeaning,
  generateNextJapaneseSentence,
  generateSdxlPromptsFromSentences,
  translateJapaneseSentenceToKorean,
} from './llm';
import type { EditorAudio, EditorWord, EditorWordSkill, ExampleDraft } from './types';

const SIMILARITY_THRESHOLD = 0.95;
const USE_TEMPORARY_CSV_AUTO_FLOW_SEED = true;

const randomSingleListRequest: GetListRequest = {
  offset: 0,
  limit: 1,
  selected_ids: [],
  search_text: null,
  text_filter: {},
  filter: {},
  sort: null,
  random: true,
};

const lowSimilarityListRequest: GetListRequest = {
  offset: 0,
  limit: 10,
  selected_ids: [],
  search_text: null,
  text_filter: {},
  filter: {},
  sort: ['similar_text_context_example_score', 'asc'],
  random: false,
};

const lowExampleCountWordListRequest: GetListRequest = {
  offset: 0,
  limit: 10,
  selected_ids: [],
  search_text: null,
  text_filter: {},
  filter: {},
  sort: ['examples', 'asc'],
  random: false,
};

const initialDraft: ExampleDraft = {
  sourceSentence: '',
  seedWord: '',
  generatedSentence: '',
  krMeaning: '',
  speaker: '',
  tone: '',
  positivePrompt: '',
  negativePrompt: '',
};

type ExampleEditorProviderProps = {
  children: ReactNode;
};

export function ExampleEditorProvider({ children }: ExampleEditorProviderProps) {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const isAdmin = user?.roles.includes('admin') ?? false;
  const [draft, setDraft] = useState<ExampleDraft>(initialDraft);
  const draftRef = useRef(initialDraft);
  const [words, setWords] = useState<EditorWord[]>([]);
  const [audios, setAudios] = useState<EditorAudio[]>([]);
  const [selectedWordId, setSelectedWordId] = useState<string | null>(null);
  const [isWordModalOpen, setIsWordModalOpen] = useState(false);
  const [isExtractingWords, setIsExtractingWords] = useState(false);
  const [extractionError, setExtractionError] = useState<string | null>(null);
  const [isGeneratingSentence, setIsGeneratingSentence] = useState(false);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [isTranslatingMeaning, setIsTranslatingMeaning] = useState(false);
  const [translationError, setTranslationError] = useState<string | null>(null);
  const [isPickingRandomExample, setIsPickingRandomExample] = useState(false);
  const [randomExampleError, setRandomExampleError] = useState<string | null>(null);
  const [isLoadingLowSimilarityExamples, setIsLoadingLowSimilarityExamples] = useState(false);
  const [lowSimilarityExampleError, setLowSimilarityExampleError] = useState<string | null>(null);
  const [lowSimilarityExamples, setLowSimilarityExamples] = useState<LowSimilarityExampleCandidate[]>([]);
  const [isLowSimilarityPickerOpen, setIsLowSimilarityPickerOpen] = useState(false);
  const [isPickingRandomWord, setIsPickingRandomWord] = useState(false);
  const [randomWordError, setRandomWordError] = useState<string | null>(null);
  const [isLoadingLowExampleCountWords, setIsLoadingLowExampleCountWords] = useState(false);
  const [lowExampleCountWordError, setLowExampleCountWordError] = useState<string | null>(null);
  const [lowExampleCountWords, setLowExampleCountWords] = useState<LowExampleCountWordCandidate[]>([]);
  const [isLowExampleCountWordPickerOpen, setIsLowExampleCountWordPickerOpen] = useState(false);
  const [deletingLowExampleCountWordId, setDeletingLowExampleCountWordId] =
    useState<number | null>(null);
  const [pendingExampleSave, setPendingExampleSave] =
    useState<PendingExampleSave | null>(null);
  const [isPreparingExampleSave, setIsPreparingExampleSave] = useState(false);
  const [isConfirmingExampleSave, setIsConfirmingExampleSave] = useState(false);
  const [exampleSaveError, setExampleSaveError] = useState<string | null>(null);
  const [savedExampleId, setSavedExampleId] = useState<number | null>(null);
  const [isGeneratingPrompt, setIsGeneratingPrompt] = useState(false);
  const [promptError, setPromptError] = useState<string | null>(null);
  const [isGeneratingImage, setIsGeneratingImage] = useState(false);
  const [isRecommendingImage, setIsRecommendingImage] = useState(false);
  const [isSavingImage, setIsSavingImage] = useState(false);
  const [imageGenerationError, setImageGenerationError] = useState<string | null>(null);
  const [imageRecommendationError, setImageRecommendationError] = useState<string | null>(null);
  const [imageSaveError, setImageSaveError] = useState<string | null>(null);
  const [imageSaveMessage, setImageSaveMessage] = useState<string | null>(null);
  const [generatedPreview, setGeneratedPreview] =
    useState<GeneratedImagePreview | null>(null);
  const [recommendedImage, setRecommendedImage] = useState<RecommendedImage | null>(null);
  const [isLoadingAudios, setIsLoadingAudios] = useState(false);
  const [audioAutoGenerateRequestKey, setAudioAutoGenerateRequestKey] = useState(0);
  const [deletingAudioId, setDeletingAudioId] = useState<string | null>(null);
  const [audioListError, setAudioListError] = useState<string | null>(null);
  const [audioDeleteError, setAudioDeleteError] = useState<string | null>(null);
  const [audioSaveMessage, setAudioSaveMessage] = useState<string | null>(null);
  const [isRunningAutoFlow, setIsRunningAutoFlow] = useState(false);
  const [autoFlowStep, setAutoFlowStep] = useState<string | null>(null);
  const [autoFlowError, setAutoFlowError] = useState<string | null>(null);
  const generatedPreviewUrlRef = useRef<string | null>(null);
  const isMountedRef = useRef(true);
  const selectedWord = words.find((word) => word.id === selectedWordId) ?? null;
  const selectedWordCanSaveSkill = selectedWord
    ? selectedWord.wordId != null || (isAdmin && selectedWord.lemmaId != null)
    : false;
  const cannotExtractWords = isExtractingWords || !authReady || !draft.generatedSentence.trim();
  const previewSrc = generatedPreview?.url ?? recommendedImage?.src ?? null;
  const previewAlt = generatedPreview
    ? `generated image seed ${generatedPreview.seed}`
    : recommendedImage?.title;
  const currentImagePrompt = generatedPreview?.prompt ?? recommendedImage?.prompt ?? '';
  const currentImageNegativePrompt =
    generatedPreview?.negativePrompt ?? recommendedImage?.negativePrompt ?? '';
  const currentImageScoreLabel = recommendedImage?.scoreLabel ?? null;
  const cannotGeneratePrompt =
    isGeneratingPrompt || !draft.sourceSentence.trim() || !draft.generatedSentence.trim();
  const cannotGenerateImage = isGeneratingImage || !draft.positivePrompt.trim();
  const cannotRecommendImage = isRecommendingImage || !draft.positivePrompt.trim();
  const canSaveImage =
    authReady
    && isAdmin
    && !isSavingImage
    && generatedPreview != null
    && Boolean(generatedPreview.prompt.trim());
  const isSavingExample = isPreparingExampleSave || isConfirmingExampleSave;
  const canSaveExample =
    authReady
    && isAdmin
    && Boolean(draft.generatedSentence.trim())
    && Boolean(draft.krMeaning.trim())
    && Boolean(draft.positivePrompt.trim())
    && pendingExampleSave == null;
  const cannotRunAutoFlow =
    isRunningAutoFlow
    || !authReady
    || isGeneratingSentence
    || isTranslatingMeaning
    || isPickingRandomExample
    || isLoadingLowSimilarityExamples
    || isPickingRandomWord
    || isLoadingLowExampleCountWords
    || isSavingExample
    || isExtractingWords
    || isGeneratingPrompt
    || isRecommendingImage
    || isSavingImage
    || pendingExampleSave != null;

  const setDraftValue = useCallback((nextDraft: ExampleDraft) => {
    const currentDraft = draftRef.current;
    if (
      currentDraft.sourceSentence !== nextDraft.sourceSentence
      || currentDraft.generatedSentence !== nextDraft.generatedSentence
      || currentDraft.krMeaning !== nextDraft.krMeaning
    ) {
      setSavedExampleId(null);
    }

    draftRef.current = nextDraft;
    setDraft(nextDraft);
  }, []);

  const patchDraft = useCallback((nextFields: Partial<ExampleDraft>) => {
    setDraftValue({
      ...draftRef.current,
      ...nextFields,
    });
  }, [setDraftValue]);

  const setDraftField = <Field extends keyof ExampleDraft,>(
    field: Field,
    value: ExampleDraft[Field],
  ) => {
    patchDraft({ [field]: value });
  };

  const fetchSavedAudios = useCallback(async () => {
    if (savedExampleId == null) {
      return [];
    }

    const response = await dbTables.Audio.listRows({
      offset: 0,
      limit: 20,
      selected_ids: [],
      search_text: null,
      text_filter: {},
      filter: { example_id: [savedExampleId, savedExampleId] },
      sort: ['id', 'desc'],
    });

    return response.items.map((audio): EditorAudio => {
      const id = String(audio.id ?? audio.object_key ?? 'audio');

      return {
        id,
        speaker: audio.speaker,
        filename: `audio-${id}.wav`,
        createdAt: audio.created_at ?? '',
        src: audio.object_key ?? null,
      };
    });
  }, [savedExampleId]);

  const refreshSavedAudios = useCallback(async () => {
    setIsLoadingAudios(true);
    setAudioListError(null);

    try {
      const nextAudios = await fetchSavedAudios();
      setAudios(nextAudios);
    } catch (error) {
      setAudioListError(
        error instanceof Error ? error.message : '저장된 오디오를 불러오지 못했습니다.',
      );
    } finally {
      setIsLoadingAudios(false);
    }
  }, [fetchSavedAudios]);

  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
      if (generatedPreviewUrlRef.current) {
        URL.revokeObjectURL(generatedPreviewUrlRef.current);
      }
    };
  }, []);

  useEffect(() => {
    queueMicrotask(() => {
      void refreshSavedAudios();
    });
  }, [refreshSavedAudios]);

  const fetchRandomExampleText = async () => {
    const response = await dbTables.Example.listRows(randomSingleListRequest);
    const example = response.items[0] ?? null;
    const jpText = example?.jp_text.trim() ?? '';

    if (!jpText) {
      throw new Error('무작위 예문을 찾지 못했습니다.');
    }

    return jpText;
  };

  const fetchLowSimilarityExamples = async (): Promise<LowSimilarityExampleCandidate[]> => {
    const response = await dbTables.CreatorHelpers.listExampleRowsSortSimilar(
      lowSimilarityListRequest,
    );
    const baseCandidates = response.items.flatMap((item) => {
      const id = item.id;
      const jpText = item.jp_text.trim();

      if (id == null || !jpText) {
        return [];
      }

      return [{
        id,
        jpText,
        similarityScore: item.similar_text_context_example?.score ?? null,
        targetId: item.similar_text_context_example?.id ?? null,
      }];
    });
    const targetIds = Array.from(new Set(
      baseCandidates
        .map((candidate) => candidate.targetId)
        .filter((id): id is number => id != null),
    ));
    const targetsById = new Map<number, ExampleRecord>();

    if (targetIds.length > 0) {
      const targetResponse = await dbTables.Example.listRows({
        offset: 0,
        limit: targetIds.length,
        selected_ids: targetIds,
        search_text: null,
        text_filter: {},
        filter: {},
        sort: null,
      });

      targetResponse.items.forEach((target) => {
        if (target.id != null) {
          targetsById.set(target.id, target);
        }
      });
    }

    return baseCandidates.map((candidate) => ({
      ...candidate,
      targetJpText: candidate.targetId == null
        ? null
        : targetsById.get(candidate.targetId)?.jp_text.trim() || null,
    }));
  };

  const fetchRandomWordLemma = async () => {
    const response = await dbTables.JpWord.listRowsWithProns(randomSingleListRequest);
    const word = response.items[0] ?? null;
    const lemma = word?.lemma.trim() ?? '';

    if (!lemma) {
      throw new Error('무작위 단어를 찾지 못했습니다.');
    }

    return lemma;
  };

  const fetchTemporaryAutoFlowSeed = async () => {
    const response = await dbTables.CreatorHelpers.popTemporaryAutoFlowSeed();
    const sourceSentence = response.source_sentence.trim();
    const seedWord = response.seed_word.trim();

    if (!sourceSentence || !seedWord) {
      throw new Error('CSV 자동 생성 입력을 가져오지 못했습니다.');
    }

    return { sourceSentence, seedWord };
  };

  const fetchLowExampleCountWords = async (): Promise<LowExampleCountWordCandidate[]> => {
    const response = await dbTables.JpWord.listRowsWithProns(lowExampleCountWordListRequest);

    return response.items.flatMap((word) => {
      const id = word.id;
      const lemma = word.lemma.trim();

      if (id == null || !lemma) {
        return [];
      }

      return [{
        id,
        lemma,
        krMean: word.kr_mean.trim(),
        exampleCount: word.examples?.length ?? 0,
      }];
    });
  };

  const generateSentence = async () => {
    if (isGeneratingSentence) {
      return;
    }

    setIsGeneratingSentence(true);
    setGenerationError(null);

    try {
      const currentDraft = draftRef.current;
      const generatedSentence = await generateNextJapaneseSentence(
        currentDraft.sourceSentence,
        currentDraft.seedWord,
      );
      patchDraft({ generatedSentence });
    } catch (error) {
      setGenerationError(
        error instanceof Error ? error.message : '일본어 문장 생성에 실패했습니다.',
      );
    } finally {
      setIsGeneratingSentence(false);
    }
  };

  const translateMeaning = async () => {
    if (isTranslatingMeaning) {
      return;
    }

    setIsTranslatingMeaning(true);
    setTranslationError(null);

    try {
      const krMeaning = await translateJapaneseSentenceToKorean(
        draftRef.current.generatedSentence,
      );
      patchDraft({ krMeaning });
    } catch (error) {
      setTranslationError(
        error instanceof Error ? error.message : '한국어 번역에 실패했습니다.',
      );
    } finally {
      setIsTranslatingMeaning(false);
    }
  };

  const pickRandomExample = async () => {
    if (isPickingRandomExample) {
      return;
    }

    setIsPickingRandomExample(true);
    setRandomExampleError(null);

    try {
      patchDraft({ sourceSentence: await fetchRandomExampleText() });
    } catch (error) {
      setRandomExampleError(
        error instanceof Error ? error.message : '무작위 예문을 찾지 못했습니다.',
      );
    } finally {
      setIsPickingRandomExample(false);
    }
  };

  const openLowSimilarityPicker = async () => {
    if (isLoadingLowSimilarityExamples) {
      return;
    }

    setIsLowSimilarityPickerOpen(true);
    setIsLoadingLowSimilarityExamples(true);
    setLowSimilarityExampleError(null);
    setLowSimilarityExamples([]);
    setRandomExampleError(null);

    try {
      setLowSimilarityExamples(await fetchLowSimilarityExamples());
    } catch (error) {
      setLowSimilarityExamples([]);
      setLowSimilarityExampleError(
        error instanceof Error ? error.message : '낮은 유사도 예문을 불러오지 못했습니다.',
      );
    } finally {
      setIsLoadingLowSimilarityExamples(false);
    }
  };

  const closeLowSimilarityPicker = () => {
    setIsLowSimilarityPickerOpen(false);
  };

  const selectLowSimilarityExample = (candidate: LowSimilarityExampleCandidate) => {
    patchDraft({ sourceSentence: candidate.jpText });
    setLowSimilarityExampleError(null);
    setIsLowSimilarityPickerOpen(false);
  };

  const pickRandomWord = async () => {
    if (isPickingRandomWord) {
      return;
    }

    setIsPickingRandomWord(true);
    setRandomWordError(null);

    try {
      patchDraft({ seedWord: await fetchRandomWordLemma() });
    } catch (error) {
      setRandomWordError(
        error instanceof Error ? error.message : '무작위 단어를 찾지 못했습니다.',
      );
    } finally {
      setIsPickingRandomWord(false);
    }
  };

  const openLowExampleCountWordPicker = async () => {
    if (isLoadingLowExampleCountWords) {
      return;
    }

    setIsLowExampleCountWordPickerOpen(true);
    setIsLoadingLowExampleCountWords(true);
    setLowExampleCountWordError(null);
    setLowExampleCountWords([]);
    setRandomWordError(null);

    try {
      setLowExampleCountWords(await fetchLowExampleCountWords());
    } catch (error) {
      setLowExampleCountWords([]);
      setLowExampleCountWordError(
        error instanceof Error ? error.message : '예문 수가 적은 단어를 불러오지 못했습니다.',
      );
    } finally {
      setIsLoadingLowExampleCountWords(false);
    }
  };

  const closeLowExampleCountWordPicker = () => {
    setIsLowExampleCountWordPickerOpen(false);
  };

  const selectLowExampleCountWord = (candidate: LowExampleCountWordCandidate) => {
    patchDraft({ seedWord: candidate.lemma });
    setLowExampleCountWordError(null);
    setIsLowExampleCountWordPickerOpen(false);
  };

  const deleteLowExampleCountWord = async (candidateId: number) => {
    if (deletingLowExampleCountWordId != null) {
      return;
    }

    if (!authReady) {
      setLowExampleCountWordError('사용자 정보를 확인 중입니다.');
      return;
    }

    if (!isAdmin) {
      setLowExampleCountWordError('admin 권한이 있어야 단어를 삭제할 수 있습니다.');
      return;
    }

    setDeletingLowExampleCountWordId(candidateId);
    setLowExampleCountWordError(null);

    try {
      await dbTables.JpWord.deleteRows([candidateId]);
      setLowExampleCountWords((currentWords) =>
        currentWords.filter((candidate) => candidate.id !== candidateId),
      );
      setWords((currentWords) => currentWords.filter((word) => word.wordId !== candidateId));
      setSelectedWordId((currentSelectedWordId) => {
        const currentSelectedWord = words.find((word) => word.id === currentSelectedWordId);
        return currentSelectedWord?.wordId === candidateId ? null : currentSelectedWordId;
      });
    } catch (error) {
      setLowExampleCountWordError(
        error instanceof Error ? error.message : '단어를 삭제하지 못했습니다.',
      );
    } finally {
      setDeletingLowExampleCountWordId(null);
    }
  };

  const extractWordsFromText = async (text: string) => {
    const normalizedText = text.trim();
    if (!normalizedText) {
      throw new Error('일본어 문장이 없습니다.');
    }

    setIsExtractingWords(true);
    setExtractionError(null);

    try {
      const requestSkills = user ? undefined : getGuestJapaneseTextSkills();
      const response = await dbTables.JpWord.analyzeJapaneseText(
        normalizedText,
        requestSkills,
      );
      setWords(
        response.words.map((word): EditorWord => {
          const userWordSkill: EditorWordSkill | null = word.userWordSkill
            ? {
                id: word.userWordSkill.id ?? null,
                userId: word.userWordSkill.user_id ?? null,
                wordId: word.userWordSkill.word_id,
                reading: word.userWordSkill.reading,
                listening: word.userWordSkill.listening,
                speaking: word.userWordSkill.speaking,
                createdAt: word.userWordSkill.created_at ?? null,
                updatedAt: word.userWordSkill.updated_at ?? null,
              }
            : null;

          return {
            id: word.id,
            wordId: word.word_id,
            lemmaId: word.lemma_id,
            surface: word.surface,
            lemma: word.lemma,
            jpPron: word.jpPron,
            krMean: word.krMean,
            userWordSkill,
          };
        }),
      );
      setSelectedWordId(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : '형태소 추출에 실패했습니다.';
      setExtractionError(message);
      throw new Error(message);
    } finally {
      setIsExtractingWords(false);
    }
  };

  const extractWords = async () => {
    if (cannotExtractWords) {
      return;
    }

    try {
      await extractWordsFromText(draftRef.current.generatedSentence);
    } catch {
      // extractWordsFromText already exposes the Korean error message in shared state.
    }
  };

  const openNewWordModal = () => {
    setSelectedWordId(null);
    setIsWordModalOpen(true);
  };

  const openWordModal = (wordId: string) => {
    setSelectedWordId(wordId);
    setIsWordModalOpen(true);
  };

  const submitWord = async (word: WordInputModalValue) => {
    if (!authReady) {
      throw new Error('사용자 정보를 확인 중입니다.');
    }
    if (!selectedWord || !word.id) {
      return;
    }

    const parsedReading = Number(word.reading);
    const reading = Number.isFinite(parsedReading)
      ? Math.max(0, Math.min(100, Math.round(parsedReading)))
      : 0;
    const currentSkill = selectedWord.userWordSkill;
    let persistedWordId = selectedWord.wordId;
    let lemma = selectedWord.lemma;
    let krMean = selectedWord.krMean;

    if (isAdmin) {
      const lemmaId = selectedWord.lemmaId ?? word.lemmaId;
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

    let nextSkill: EditorWordSkill = {
      id: currentSkill?.id ?? null,
      userId: currentSkill?.userId ?? user?.id ?? null,
      wordId: persistedWordId,
      reading,
      listening: currentSkill?.listening ?? 0,
      speaking: currentSkill?.speaking ?? 0,
      createdAt: currentSkill?.createdAt ?? null,
      updatedAt: new Date().toISOString(),
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
        userId: user.id,
      };
    } else {
      const savedSkill = saveGuestJapaneseWordSkill(persistedWordId, reading);
      nextSkill = {
        ...nextSkill,
        updatedAt: savedSkill.updated_at,
      };
    }

    setWords((currentWords) =>
      currentWords.map((currentWord) => (
        currentWord.id === selectedWord.id
          ? {
              ...currentWord,
              wordId: persistedWordId,
              lemma,
              krMean,
              userWordSkill: nextSkill,
            }
          : currentWord
      )),
    );
    setSelectedWordId(selectedWord.id);
  };

  const deleteWord = async (wordId: number) => {
    await dbTables.JpWord.deleteRows([wordId]);
    setWords((currentWords) => currentWords.filter((word) => word.wordId !== wordId));
    setSelectedWordId(null);
  };

  const fetchSelectedWordMeaning = async () => {
    if (!selectedWord) {
      throw new Error('뜻을 가져올 단어를 선택해 주세요.');
    }

    const sentence = draftRef.current.generatedSentence.trim();
    const surface = selectedWord.surface.trim();
    const lemma = selectedWord.lemma.trim();

    if (!sentence) {
      throw new Error('일본어 문장이 없습니다.');
    }
    if (!surface || !lemma) {
      throw new Error('단어 정보가 부족합니다.');
    }

    return fetchJapaneseWordKoreanMeaning({
      sentence,
      koreanSentenceMeaning: draftRef.current.krMeaning,
      surface,
      lemma,
    });
  };

  const generatePromptForSentences = async (sourceSentence: string, generatedSentence: string) => {
    setIsGeneratingPrompt(true);
    setPromptError(null);

    try {
      const prompts = await generateSdxlPromptsFromSentences(
        sourceSentence,
        generatedSentence,
      );
      patchDraft({
        positivePrompt: prompts.positivePrompt,
        negativePrompt: prompts.negativePrompt+", low quality, blurry, jpeg artifacts, watermark, signature, text, logo, distorted, deformed face",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'SDXL 프롬프트 생성에 실패했습니다.';
      setPromptError(message);
      throw new Error(message);
    } finally {
      setIsGeneratingPrompt(false);
    }
  };

  const generatePrompt = async () => {
    if (cannotGeneratePrompt) {
      return;
    }

    try {
      await generatePromptForSentences(
        draftRef.current.sourceSentence,
        draftRef.current.generatedSentence,
      );
    } catch {
      // generatePromptForSentences already exposes the Korean error message in shared state.
    }
  };

  const recommendImage = async () => {
    if (cannotRecommendImage) {
      return;
    }

    setIsRecommendingImage(true);
    setImageRecommendationError(null);
    setImageGenerationError(null);
    setImageSaveError(null);
    setImageSaveMessage(null);
    setRecommendedImage(null);
    if (generatedPreviewUrlRef.current) {
      URL.revokeObjectURL(generatedPreviewUrlRef.current);
      generatedPreviewUrlRef.current = null;
    }
    setGeneratedPreview(null);

    try {
      const prompt = draftRef.current.positivePrompt.trim();
      const { embedding } = await aiFastApi.embeddings({ text: prompt });
      const [similarImage] = await dbTables.CreatorHelpers.findSimilarImagesByPromptEmbedding(
        embedding,
        1,
      );

      if (!similarImage) {
        throw new Error('추천할 이미지를 찾지 못했습니다.');
      }

      const response = await dbTables.Image.listRows({
        offset: 0,
        limit: 1,
        selected_ids: [similarImage.id],
        search_text: null,
        text_filter: {},
        filter: {},
        sort: null,
      });
      const imageRecord =
        response.items.find((item) => item.id === similarImage.id)
        ?? response.items[0]
        ?? null;

      if (!imageRecord?.id) {
        throw new Error('추천 이미지 정보를 불러오지 못했습니다.');
      }

      setRecommendedImage({
        id: imageRecord.id,
        title: `image-${imageRecord.id}`,
        prompt: imageRecord.prompt ?? '',
        negativePrompt: imageRecord.negative_prompt ?? '',
        score: similarImage.score,
        scoreLabel: `${(similarImage.score * 100).toFixed(1)}%`,
        src: imageRecord.object_key ?? null,
      });
    } catch (error) {
      setImageRecommendationError(
        error instanceof Error ? error.message : '이미지를 추천하지 못했습니다.',
      );
    } finally {
      setIsRecommendingImage(false);
    }
  };

  const generateImage = async () => {
    if (cannotGenerateImage) {
      return;
    }

    setIsGeneratingImage(true);
    setImageRecommendationError(null);
    setImageGenerationError(null);
    setImageSaveError(null);
    setImageSaveMessage(null);

    try {
      const currentDraft = draftRef.current;
      const prompt = currentDraft.positivePrompt.trim();
      const negativePrompt = currentDraft.negativePrompt.trim();
      const response = await aiFastApi.sdxlT2i({
        prompts: [prompt],
        negative_prompts: [negativePrompt],
        ...SDXL_IMAGE_GENERATION_PARAMS,
      });
      const image = response.images[0] ?? null;

      if (!image?.image_base64) {
        throw new Error('생성된 이미지가 없습니다.');
      }

      const binary = atob(image.image_base64);
      const bytes = new Uint8Array(binary.length);

      for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
      }

      const fileMetadata = getGeneratedImageFileMetadata(image.format);
      const blob = new Blob([bytes], { type: fileMetadata.mimeType });
      const url = URL.createObjectURL(blob);

      if (generatedPreviewUrlRef.current) {
        URL.revokeObjectURL(generatedPreviewUrlRef.current);
      }
      generatedPreviewUrlRef.current = url;
      setRecommendedImage(null);
      setGeneratedPreview({
        blob,
        prompt,
        negativePrompt,
        seed: image.seed,
        format: fileMetadata.format,
        extension: fileMetadata.extension,
        mimeType: fileMetadata.mimeType,
        url,
      });
    } catch (error) {
      setImageGenerationError(
        error instanceof Error ? error.message : 'SDXL 이미지 생성에 실패했습니다.',
      );
    } finally {
      setIsGeneratingImage(false);
    }
  };

  const saveImage = async () => {
    if (!generatedPreview || isSavingImage) {
      return;
    }

    if (!authReady) {
      setImageSaveError('사용자 정보를 확인 중입니다.');
      return;
    }

    if (!isAdmin) {
      setImageSaveError('admin 권한이 있어야 이미지를 저장할 수 있습니다.');
      return;
    }

    const prompt = generatedPreview.prompt.trim();
    const negativePrompt = generatedPreview.negativePrompt.trim();
    if (!prompt) {
      setImageSaveError('저장할 이미지 positive prompt가 없습니다.');
      return;
    }

    setIsSavingImage(true);
    setImageSaveError(null);
    setImageSaveMessage(null);

    try {
      const { embedding: promptEmbedding } = await aiFastApi.embeddings({ text: prompt });
      const file = new File(
        [generatedPreview.blob],
        `sdxl-${generatedPreview.seed}-${Date.now()}.${generatedPreview.extension}`,
        { type: generatedPreview.blob.type || generatedPreview.mimeType },
      );
      await dbTables.Image.upsertFormRow(
        {
          prompt,
          negative_prompt: negativePrompt || null,
          prompt_embedding: promptEmbedding,
        },
        { object_key: file },
      );
      setImageSaveMessage('이미지를 저장했습니다.');
    } catch (error) {
      setImageSaveError(error instanceof Error ? error.message : '이미지를 저장하지 못했습니다.');
    } finally {
      setIsSavingImage(false);
    }
  };

  const deleteSavedAudio = async (audioId: string) => {
    if (!authReady) {
      setAudioDeleteError('사용자 정보를 확인 중입니다.');
      return;
    }
    if (!isAdmin) {
      setAudioDeleteError('admin 권한이 있어야 오디오를 삭제할 수 있습니다.');
      return;
    }
    if (savedExampleId == null) {
      setAudioDeleteError('저장된 예문이 있어야 오디오를 삭제할 수 있습니다.');
      return;
    }
    if (deletingAudioId != null) {
      return;
    }

    const parsedAudioId = Number(audioId);
    if (!Number.isInteger(parsedAudioId)) {
      setAudioDeleteError('삭제할 오디오 ID가 올바르지 않습니다.');
      return;
    }

    setDeletingAudioId(audioId);
    setAudioDeleteError(null);
    setAudioSaveMessage(null);

    try {
      await dbTables.Audio.deleteRows([parsedAudioId]);
      await refreshSavedAudios();
      setAudioSaveMessage('오디오를 삭제했습니다.');
    } catch (error) {
      setAudioDeleteError(error instanceof Error ? error.message : '오디오를 삭제하지 못했습니다.');
    } finally {
      setDeletingAudioId(null);
    }
  };

  const prepareExampleSave = async () => {
    if (isSavingExample || pendingExampleSave) {
      return;
    }

    if (!authReady) {
      setExampleSaveError('사용자 정보를 확인 중입니다.');
      return;
    }

    if (!isAdmin) {
      setExampleSaveError('admin 권한이 있어야 예문을 저장할 수 있습니다.');
      return;
    }

    const currentDraft = draftRef.current;
    const jpText = currentDraft.generatedSentence.trim();
    const krText = currentDraft.krMeaning.trim();
    const sourceText = currentDraft.sourceSentence.trim();
    const prompt = currentDraft.positivePrompt.trim();
    const negativePrompt = currentDraft.negativePrompt.trim();

    if (!jpText || !krText) {
      setExampleSaveError('일본어 문장과 한국어 뜻을 입력해 주세요.');
      return;
    }

    if (!prompt) {
      setExampleSaveError('SDXL positive prompt를 입력해 주세요.');
      return;
    }

    setIsPreparingExampleSave(true);
    setExampleSaveError(null);

    try {
      const { embedding: textEmbedding } = await aiFastApi.embeddings({ text: jpText });
      const { embedding: promptEmbedding } = await aiFastApi.embeddings({ text: prompt });
      const similarResults = await dbTables.CreatorHelpers.findSimilarExamplesByEmbedding(
        textEmbedding,
        1,
      );
      const bestSimilarity = similarResults[0] ?? null;
      let candidate: PendingExampleSave['candidate'] = null;

      if (bestSimilarity && bestSimilarity.score >= SIMILARITY_THRESHOLD) {
        const candidateResponse = await dbTables.Example.listRows({
          offset: 0,
          limit: 1,
          selected_ids: [bestSimilarity.id],
          search_text: null,
          text_filter: {},
          filter: {},
          sort: null,
        });
        const candidateExample =
          candidateResponse.items.find((item) => item.id === bestSimilarity.id)
          ?? candidateResponse.items[0]
          ?? null;

        if (candidateExample?.id != null) {
          candidate = {
            id: candidateExample.id,
            score: bestSimilarity.score,
            example: candidateExample,
          };
        }
      }

      setPendingExampleSave({
        jpText,
        krText,
        sourceText,
        prompt,
        negativePrompt,
        textEmbedding,
        promptEmbedding,
        candidate,
      });
    } catch (error) {
      setExampleSaveError(
        error instanceof Error ? error.message : '예문 저장 준비에 실패했습니다.',
      );
    } finally {
      setIsPreparingExampleSave(false);
    }
  };

  const confirmExampleSave = async (exampleId?: number) => {
    if (!pendingExampleSave || isConfirmingExampleSave) {
      return;
    }

    setIsConfirmingExampleSave(true);
    setExampleSaveError(null);

    try {
      const payload: ExampleRecord = {
        ...(exampleId != null ? { id: exampleId } : {}),
        jp_text: pendingExampleSave.jpText,
        kr_text: pendingExampleSave.krText,
        context: pendingExampleSave.sourceText || null,
        prompt: pendingExampleSave.prompt || null,
        negative_prompt: pendingExampleSave.negativePrompt || null,
        text_embedding: pendingExampleSave.textEmbedding,
        prompt_embedding: pendingExampleSave.promptEmbedding,
      };

      if (pendingExampleSave.sourceText) {
        const { embedding: contextEmbedding } = await aiFastApi.embeddings({
          text: pendingExampleSave.sourceText,
        });
        payload.context_embedding = contextEmbedding;
      }

      const [response] = await dbTables.Example.upsertRow([payload]);
      const nextExampleId = response?.id ?? exampleId ?? null;
      if (nextExampleId == null) {
        throw new Error('예문 저장 응답에 ID가 없습니다.');
      }

      setSavedExampleId(nextExampleId);
      setPendingExampleSave(null);
    } catch (error) {
      setExampleSaveError(
        error instanceof Error ? error.message : '예문을 저장하지 못했습니다.',
      );
    } finally {
      setIsConfirmingExampleSave(false);
    }
  };

  const closeExampleSaveModal = () => {
    if (isConfirmingExampleSave) {
      return;
    }

    setPendingExampleSave(null);
    setExampleSaveError(null);
  };

  const runAutoFlow = async () => {
    if (cannotRunAutoFlow) {
      return;
    }

    setIsRunningAutoFlow(true);
    setAutoFlowError(null);
    setGenerationError(null);
    setTranslationError(null);
    setRandomExampleError(null);
    setLowSimilarityExampleError(null);
    setRandomWordError(null);
    setLowExampleCountWordError(null);
    setExampleSaveError(null);
    setPromptError(null);
    setExtractionError(null);
    setAudioDeleteError(null);
    setSavedExampleId(null);

    try {
      let sourceSentence = '';
      let seedWord = '';

      if (USE_TEMPORARY_CSV_AUTO_FLOW_SEED) {
        setAutoFlowStep('CSV 입력');
        setIsLoadingLowSimilarityExamples(true);
        setIsLoadingLowExampleCountWords(true);

        const seed = await fetchTemporaryAutoFlowSeed();
        sourceSentence = seed.sourceSentence;
        seedWord = seed.seedWord;
        patchDraft({
          sourceSentence,
          seedWord,
          generatedSentence: '',
          krMeaning: '',
        });
        setIsLoadingLowSimilarityExamples(false);
        setIsLoadingLowExampleCountWords(false);
      } else {
        setAutoFlowStep('낮은 유사도 문장');
        setIsLoadingLowSimilarityExamples(true);
        const lowSimilarityCandidates = await fetchLowSimilarityExamples();
        const sourceCandidate =
          lowSimilarityCandidates[Math.floor(Math.random() * lowSimilarityCandidates.length)]
          ?? null;

        if (!sourceCandidate) {
          throw new Error('낮은 유사도 예문을 찾지 못했습니다.');
        }

        sourceSentence = sourceCandidate.jpText;
        patchDraft({
          sourceSentence,
          generatedSentence: '',
          krMeaning: '',
        });
        setIsLoadingLowSimilarityExamples(false);

        setAutoFlowStep('예문 적은 단어');
        setIsLoadingLowExampleCountWords(true);
        const lowExampleCountCandidates = await fetchLowExampleCountWords();
        const wordCandidate =
          lowExampleCountCandidates[Math.floor(Math.random() * lowExampleCountCandidates.length)]
          ?? null;

        if (!wordCandidate) {
          throw new Error('예문 수가 적은 단어를 찾지 못했습니다.');
        }

        seedWord = wordCandidate.lemma;
        patchDraft({
          sourceSentence,
          seedWord,
          generatedSentence: '',
          krMeaning: '',
        });
        setIsLoadingLowExampleCountWords(false);
      }

      setAutoFlowStep('문장 생성');
      setIsGeneratingSentence(true);
      const generatedSentence = await generateNextJapaneseSentence(sourceSentence, seedWord);
      patchDraft({
        sourceSentence,
        seedWord,
        generatedSentence,
        krMeaning: '',
      });
      setIsGeneratingSentence(false);

      setAutoFlowStep('한국어 번역');
      setIsTranslatingMeaning(true);
      const krMeaning = await translateJapaneseSentenceToKorean(generatedSentence);
      patchDraft({
        sourceSentence,
        seedWord,
        generatedSentence,
        krMeaning,
      });
      setIsTranslatingMeaning(false);

      setAutoFlowStep('프롬프트 생성');
      await generatePromptForSentences(sourceSentence, generatedSentence);

      setAutoFlowStep('형태소 추출');
      await extractWordsFromText(generatedSentence);

      setAutoFlowStep('오디오 생성');
      setAudioAutoGenerateRequestKey((currentKey) => currentKey + 1);
    } catch (error) {
      setAutoFlowError(
        error instanceof Error ? error.message : '자동 생성에 실패했습니다.',
      );
    } finally {
      setIsRunningAutoFlow(false);
      setAutoFlowStep(null);
      setIsPickingRandomExample(false);
      setIsLoadingLowSimilarityExamples(false);
      setIsPickingRandomWord(false);
      setIsLoadingLowExampleCountWords(false);
      setIsGeneratingSentence(false);
      setIsTranslatingMeaning(false);
    }
  };

  const contextValue = {
    session: {
      authReady,
      isAdmin,
    },
    draft: {
      value: draft,
      set: setDraftValue,
      setField: setDraftField,
    },
    sentence: {
      isGenerating: isGeneratingSentence,
      generationError,
      isTranslating: isTranslatingMeaning,
      translationError,
      isPickingRandomExample,
      randomExampleError,
      isLoadingLowSimilarityExamples,
      lowSimilarityExampleError,
      lowSimilarityExamples,
      isLowSimilarityPickerOpen,
      isPickingRandomWord,
      randomWordError,
      isLoadingLowExampleCountWords,
      lowExampleCountWordError,
      lowExampleCountWords,
      isLowExampleCountWordPickerOpen,
      deletingLowExampleCountWordId,
      isGeneratingPrompt,
      promptError,
      cannotGeneratePrompt,
      generate: generateSentence,
      translate: translateMeaning,
      pickRandomExample,
      pickRandomWord,
      openLowExampleCountWordPicker,
      closeLowExampleCountWordPicker,
      selectLowExampleCountWord,
      deleteLowExampleCountWord,
      openLowSimilarityPicker,
      closeLowSimilarityPicker,
      selectLowSimilarityExample,
      generatePrompt,
    },
    words: {
      items: words,
      selectedWordId,
      selectedWord,
      isModalOpen: isWordModalOpen,
      isExtracting: isExtractingWords,
      extractionError,
      cannotExtract: cannotExtractWords,
      selectedWordCanSaveSkill,
      extract: extractWords,
      openNewWordModal,
      openWordModal,
      closeModal: () => setIsWordModalOpen(false),
      submitWord,
      deleteWord,
      fetchSelectedWordMeaning,
    },
    image: {
      isGeneratingImage,
      isRecommending: isRecommendingImage,
      isSaving: isSavingImage,
      imageGenerationError,
      recommendationError: imageRecommendationError,
      saveError: imageSaveError,
      saveMessage: imageSaveMessage,
      generatedPreview,
      recommendedImage,
      previewSrc,
      previewAlt,
      currentPrompt: currentImagePrompt,
      currentNegativePrompt: currentImageNegativePrompt,
      currentScoreLabel: currentImageScoreLabel,
      cannotGenerateImage,
      cannotRecommendImage,
      canSave: canSaveImage,
      recommend: recommendImage,
      generateImage,
      save: saveImage,
    },
    audio: {
      audios,
      isLoadingAudios,
      autoGenerateRequestKey: audioAutoGenerateRequestKey,
      deletingAudioId,
      audioListError,
      deleteError: audioDeleteError,
      saveMessage: audioSaveMessage,
      errors: [
        audioDeleteError,
        audioListError,
      ].filter((message): message is string => Boolean(message)),
      refreshSaved: refreshSavedAudios,
      deleteSaved: deleteSavedAudio,
    },
    save: {
      pending: pendingExampleSave,
      savedExampleId,
      isPreparing: isPreparingExampleSave,
      isConfirming: isConfirmingExampleSave,
      isSaving: isSavingExample,
      canSave: canSaveExample,
      panelError: pendingExampleSave ? null : exampleSaveError,
      modalError: pendingExampleSave ? exampleSaveError : null,
      prepare: prepareExampleSave,
      confirm: confirmExampleSave,
      closeModal: closeExampleSaveModal,
    },
    autoFlow: {
      isRunning: isRunningAutoFlow,
      step: autoFlowStep,
      error: autoFlowError,
      cannotRun: cannotRunAutoFlow,
      run: runAutoFlow,
    },
  };

  return (
    <ExampleEditorContext.Provider value={contextValue}>
      {children}
    </ExampleEditorContext.Provider>
  );
}
