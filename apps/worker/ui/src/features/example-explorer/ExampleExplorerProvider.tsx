import {
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { dbTables } from '../../api/api';
import { aiFastApi, getGeneratedImageFileMetadata } from '../../api/apiAi';
import { SDXL_IMAGE_GENERATION_PARAMS } from '../../api/constants';
import type { ExampleRecord, ExampleSortSimilarRecord } from '../../api/types';
import {
  getGuestJapaneseTextSkills,
  saveGuestJapaneseWordSkill,
} from '../../api/guestJapaneseWordSkills';
import type { WordInputModalValue } from '../../components/WordInputModal';
import { useAuthStore } from '../../stores/authStore';
import { ExampleExplorerContext } from './ExampleExplorerContext';
import { useExampleList } from './hooks/useExampleList';
import {
  fetchJapaneseWordKoreanMeaning,
  generateSdxlPromptsForExample,
  translateJapaneseSentenceToKorean,
} from './llm';
import type {
  ExampleExplorerForm,
  ExplorerAudio,
  ExplorerGeneratedImagePreview,
  ExplorerRecommendedImage,
  ExplorerWord,
  ExplorerWordSkill,
} from './types';

const DEFAULT_NEGATIVE_PROMPT =
  'low quality, blurry, jpeg artifacts, watermark, signature, text, logo, distorted, deformed face';

type ExampleExplorerProviderProps = {
  children: ReactNode;
};

function createFormFromExample(example: ExampleRecord | null): ExampleExplorerForm {
  return {
    krText: example?.kr_text ?? '',
    prompt: example?.prompt ?? '',
    negativePrompt: example?.negative_prompt ?? '',
  };
}

function appendDefaultNegativePrompt(negativePrompt: string) {
  const trimmedPrompt = negativePrompt.trim();
  return trimmedPrompt
    ? `${trimmedPrompt}, ${DEFAULT_NEGATIVE_PROMPT}`
    : DEFAULT_NEGATIVE_PROMPT;
}

export function ExampleExplorerProvider({ children }: ExampleExplorerProviderProps) {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const isAdmin = user?.roles.includes('admin') ?? false;
  const list = useExampleList();
  const refreshExampleList = list.refresh;
  const [selectedExample, setSelectedExample] = useState<ExampleSortSimilarRecord | null>(null);
  const [form, setForm] = useState<ExampleExplorerForm>(createFormFromExample(null));
  const [isSavingExample, setIsSavingExample] = useState(false);
  const [isDeletingExample, setIsDeletingExample] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteMessage, setDeleteMessage] = useState<string | null>(null);
  const [isTranslating, setIsTranslating] = useState(false);
  const [translationError, setTranslationError] = useState<string | null>(null);
  const [isGeneratingPrompt, setIsGeneratingPrompt] = useState(false);
  const [promptError, setPromptError] = useState<string | null>(null);
  const [words, setWords] = useState<ExplorerWord[]>([]);
  const [selectedWordId, setSelectedWordId] = useState<string | null>(null);
  const [isWordModalOpen, setIsWordModalOpen] = useState(false);
  const [isExtractingWords, setIsExtractingWords] = useState(false);
  const [extractionError, setExtractionError] = useState<string | null>(null);
  const [audios, setAudios] = useState<ExplorerAudio[]>([]);
  const [isLoadingAudios, setIsLoadingAudios] = useState(false);
  const [audioAutoPlayKey, setAudioAutoPlayKey] = useState(0);
  const [deletingAudioId, setDeletingAudioId] = useState<string | null>(null);
  const [audioListError, setAudioListError] = useState<string | null>(null);
  const [audioDeleteError, setAudioDeleteError] = useState<string | null>(null);
  const [audioSaveMessage, setAudioSaveMessage] = useState<string | null>(null);
  const [isGeneratingImage, setIsGeneratingImage] = useState(false);
  const [isRecommendingImage, setIsRecommendingImage] = useState(false);
  const [isSavingImage, setIsSavingImage] = useState(false);
  const [imageGenerationError, setImageGenerationError] = useState<string | null>(null);
  const [imageRecommendationError, setImageRecommendationError] = useState<string | null>(null);
  const [imageSaveError, setImageSaveError] = useState<string | null>(null);
  const [imageSaveMessage, setImageSaveMessage] = useState<string | null>(null);
  const [generatedPreview, setGeneratedPreview] =
    useState<ExplorerGeneratedImagePreview | null>(null);
  const [recommendedImage, setRecommendedImage] = useState<ExplorerRecommendedImage | null>(null);
  const generatedPreviewUrlRef = useRef<string | null>(null);
  const selectedExampleId = selectedExample?.id ?? null;
  const selectedWord = words.find((word) => word.id === selectedWordId) ?? null;
  const selectedWordCanSaveSkill = selectedWord
    ? selectedWord.wordId != null || (isAdmin && selectedWord.lemmaId != null)
    : false;
  const selectedExampleText = selectedExample?.jp_text.trim() ?? '';
  const previousJapaneseSentence = selectedExample?.context?.trim() ?? '';
  const isDirty = selectedExample
    ? form.krText !== selectedExample.kr_text
      || form.prompt !== (selectedExample.prompt ?? '')
      || form.negativePrompt !== (selectedExample.negative_prompt ?? '')
    : false;
  const canSaveExample =
    Boolean(selectedExample?.id)
    && authReady
    && isAdmin
    && !isSavingExample
    && !isDeletingExample
    && Boolean(form.krText.trim());
  const canDeleteExample =
    Boolean(selectedExample?.id)
    && authReady
    && isAdmin
    && !isSavingExample
    && !isDeletingExample
    && !isTranslating
    && !isGeneratingPrompt;
  const imagePreviewSrc = generatedPreview?.url ?? recommendedImage?.src ?? null;
  const imagePreviewAlt = generatedPreview
    ? `generated image seed ${generatedPreview.seed}`
    : recommendedImage?.title;
  const currentImagePrompt = generatedPreview?.prompt ?? recommendedImage?.prompt ?? form.prompt;
  const currentImageNegativePrompt =
    generatedPreview?.negativePrompt ?? recommendedImage?.negativePrompt ?? form.negativePrompt;
  const currentImageScoreLabel = recommendedImage?.scoreLabel ?? null;
  const cannotGenerateImage = isGeneratingImage || !form.prompt.trim();
  const cannotRecommendImage = isRecommendingImage || !form.prompt.trim();
  const canSaveImage =
    authReady
    && isAdmin
    && !isSavingImage
    && generatedPreview != null
    && Boolean(generatedPreview.prompt.trim());

  const selectExample = (example: ExampleSortSimilarRecord) => {
    setForm(createFormFromExample(example));
    setSaveError(null);
    setSaveMessage(null);
    setDeleteError(null);
    setDeleteMessage(null);
    setTranslationError(null);
    setPromptError(null);
    setWords([]);
    setSelectedWordId(null);
    setIsWordModalOpen(false);
    setExtractionError(null);
    setAudios([]);
    setDeletingAudioId(null);
    setAudioListError(null);
    setAudioDeleteError(null);
    setAudioSaveMessage(null);
    setImageGenerationError(null);
    setImageRecommendationError(null);
    setImageSaveError(null);
    setImageSaveMessage(null);
    setRecommendedImage(null);

    if (generatedPreviewUrlRef.current) {
      URL.revokeObjectURL(generatedPreviewUrlRef.current);
      generatedPreviewUrlRef.current = null;
    }
    setGeneratedPreview(null);

    setSelectedExample(example);
  };

  const clearSelectedExampleState = () => {
    setForm(createFormFromExample(null));
    setSaveError(null);
    setSaveMessage(null);
    setIsTranslating(false);
    setTranslationError(null);
    setIsGeneratingPrompt(false);
    setPromptError(null);
    setWords([]);
    setSelectedWordId(null);
    setIsWordModalOpen(false);
    setIsExtractingWords(false);
    setExtractionError(null);
    setAudios([]);
    setDeletingAudioId(null);
    setIsLoadingAudios(false);
    setAudioListError(null);
    setAudioDeleteError(null);
    setAudioSaveMessage(null);
    setIsGeneratingImage(false);
    setIsRecommendingImage(false);
    setIsSavingImage(false);
    setImageGenerationError(null);
    setImageRecommendationError(null);
    setImageSaveError(null);
    setImageSaveMessage(null);
    setRecommendedImage(null);

    if (generatedPreviewUrlRef.current) {
      URL.revokeObjectURL(generatedPreviewUrlRef.current);
      generatedPreviewUrlRef.current = null;
    }
    setGeneratedPreview(null);

    setSelectedExample(null);
  };

  const setFormField = <Field extends keyof ExampleExplorerForm>(
    field: Field,
    value: ExampleExplorerForm[Field],
  ) => {
    setForm((currentForm) => ({
      ...currentForm,
      [field]: value,
    }));
    setSaveMessage(null);
  };

  const loadAudiosForSelectedExample = useCallback(async () => {
    if (selectedExampleId == null) {
      return [];
    }

    const response = await dbTables.Audio.listRows({
      offset: 0,
      limit: 20,
      selected_ids: [],
      search_text: null,
      text_filter: {},
      filter: { example_id: [selectedExampleId, selectedExampleId] },
      sort: ['id', 'desc'],
    });

    return response.items.map((audio): ExplorerAudio => {
      const id = String(audio.id ?? audio.object_key ?? 'audio');

      return {
        id,
        speaker: audio.speaker,
        filename: `audio-${id}.wav`,
        createdAt: audio.created_at ?? '',
        src: audio.object_key ?? null,
      };
    });
  }, [selectedExampleId]);

  const loadSavedAudios = useCallback(async (
    options: {
      refreshList: boolean;
      syncSelectedExample: boolean;
      autoPlay: boolean;
    },
  ) => {
    setIsLoadingAudios(true);
    setAudioListError(null);

    try {
      const nextAudios = await loadAudiosForSelectedExample();
      const nextAudioIds = nextAudios
        .map((audio) => Number(audio.id))
        .filter((audioId) => Number.isInteger(audioId));

      setAudios(nextAudios);
      if (options.autoPlay && nextAudios.some((audio) => audio.src)) {
        setAudioAutoPlayKey((currentKey) => currentKey + 1);
      }
      if (options.syncSelectedExample && selectedExampleId != null) {
        setSelectedExample((currentExample) => {
          if (!currentExample || currentExample.id !== selectedExampleId) {
            return currentExample;
          }
          return { ...currentExample, audios: nextAudioIds };
        });
      }
      if (options.refreshList) {
        void refreshExampleList();
      }
    } catch (error) {
      setAudioListError(
        error instanceof Error ? error.message : '저장된 오디오를 불러오지 못했습니다.',
      );
    } finally {
      setIsLoadingAudios(false);
    }
  }, [loadAudiosForSelectedExample, refreshExampleList, selectedExampleId]);

  const refreshSavedAudios = useCallback(async () => {
    await loadSavedAudios({
      refreshList: true,
      syncSelectedExample: true,
      autoPlay: true,
    });
  }, [loadSavedAudios]);

  useEffect(() => {
    return () => {
      if (generatedPreviewUrlRef.current) {
        URL.revokeObjectURL(generatedPreviewUrlRef.current);
      }
    };
  }, []);

  useEffect(() => {
    let ignore = false;

    const analyzeSelectedExample = async () => {
      if (!selectedExampleText) {
        return;
      }

      setIsExtractingWords(true);
      setExtractionError(null);

      try {
        const requestSkills = user ? undefined : getGuestJapaneseTextSkills();
        const response = await dbTables.JpWord.analyzeJapaneseText(
          selectedExampleText,
          requestSkills,
        );

        if (ignore) {
          return;
        }

        setWords(
          response.words.map((word): ExplorerWord => {
            const userWordSkill: ExplorerWordSkill | null = word.userWordSkill
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
      } catch (error) {
        if (!ignore) {
          setExtractionError(
            error instanceof Error ? error.message : '형태소 추출에 실패했습니다.',
          );
        }
      } finally {
        if (!ignore) {
          setIsExtractingWords(false);
        }
      }
    };

    void analyzeSelectedExample();

    return () => {
      ignore = true;
    };
  }, [selectedExampleText, user]);

  useEffect(() => {
    if (selectedExampleId == null) {
      return;
    }

    queueMicrotask(() => {
      void loadSavedAudios({
        refreshList: false,
        syncSelectedExample: false,
        autoPlay: true,
      });
    });
  }, [loadSavedAudios, selectedExampleId]);

  useEffect(() => {
    let ignore = false;
    const match = selectedExample?.similar_prompt_image ?? null;

    const loadRowMatchedImage = async () => {
      if (!match) {
        setRecommendedImage(null);
        setImageRecommendationError(null);
        setIsRecommendingImage(false);
        return;
      }

      setIsRecommendingImage(true);
      setImageRecommendationError(null);

      try {
        const response = await dbTables.Image.listRows({
          offset: 0,
          limit: 1,
          selected_ids: [match.id],
          search_text: null,
          text_filter: {},
          filter: {},
          sort: null,
        });

        if (ignore) {
          return;
        }

        const imageRecord =
          response.items.find((item) => item.id === match.id)
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
          score: match.score,
          scoreLabel: `${(match.score * 100).toFixed(1)}%`,
          src: imageRecord.object_key ?? null,
        });
      } catch (error) {
        if (!ignore) {
          setImageRecommendationError(
            error instanceof Error ? error.message : '이미지를 추천하지 못했습니다.',
          );
          setRecommendedImage(null);
        }
      } finally {
        if (!ignore) {
          setIsRecommendingImage(false);
        }
      }
    };

    void loadRowMatchedImage();

    return () => {
      ignore = true;
    };
  }, [selectedExample?.similar_prompt_image]);

  const saveExample = async () => {
    if (!selectedExample?.id || isSavingExample) {
      return;
    }

    if (!authReady) {
      setSaveError('사용자 정보를 확인 중입니다.');
      return;
    }

    if (!isAdmin) {
      setSaveError('admin 권한이 있어야 예문을 저장할 수 있습니다.');
      return;
    }

    const krText = form.krText.trim();
    const prompt = form.prompt.trim();
    const negativePrompt = form.negativePrompt.trim();
    if (!krText) {
      setSaveError('한국어 뜻을 입력해 주세요.');
      return;
    }

    setIsSavingExample(true);
    setSaveError(null);
    setSaveMessage(null);

    try {
      const originalPrompt = (selectedExample.prompt ?? '').trim();
      const payload: ExampleRecord = {
        id: selectedExample.id,
        jp_text: selectedExample.jp_text,
        kr_text: krText,
        prompt: prompt || null,
        negative_prompt: negativePrompt || null,
      };

      if (prompt !== originalPrompt) {
        payload.prompt_embedding = prompt
          ? (await aiFastApi.embeddings({ text: prompt })).embedding
          : null;
      }

      const [response] = await dbTables.Example.upsertRow([payload]);
      const savedId = response?.id ?? selectedExample.id;
      const nextExample: ExampleSortSimilarRecord = {
        ...selectedExample,
        ...payload,
        id: savedId,
      };

      setSelectedExample(nextExample);
      list.updateListItem(nextExample);
      setForm(createFormFromExample(nextExample));
      setSaveMessage('예문을 저장했습니다.');
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : '예문을 저장하지 못했습니다.');
    } finally {
      setIsSavingExample(false);
    }
  };

  const deleteSelectedExample = async () => {
    if (!selectedExample?.id || isDeletingExample) {
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

    const exampleId = selectedExample.id;
    setIsDeletingExample(true);
    setDeleteError(null);
    setDeleteMessage(null);
    setSaveError(null);
    setSaveMessage(null);

    try {
      await dbTables.Example.deleteRows([exampleId]);
      clearSelectedExampleState();
      setDeleteMessage('예문을 삭제했습니다.');
      await list.refresh();
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : '예문을 삭제하지 못했습니다.');
    } finally {
      setIsDeletingExample(false);
    }
  };

  const translateMeaning = async () => {
    if (!selectedExampleText || isTranslating) {
      return;
    }

    setIsTranslating(true);
    setTranslationError(null);
    setSaveMessage(null);

    try {
      const krText = await translateJapaneseSentenceToKorean(selectedExampleText);
      setForm((currentForm) => ({
        ...currentForm,
        krText,
      }));
    } catch (error) {
      setTranslationError(
        error instanceof Error ? error.message : '한국어 번역에 실패했습니다.',
      );
    } finally {
      setIsTranslating(false);
    }
  };

  const generatePrompt = async () => {
    if (!selectedExampleText || isGeneratingPrompt) {
      return;
    }

    setIsGeneratingPrompt(true);
    setPromptError(null);
    setSaveMessage(null);

    try {
      const prompts = await generateSdxlPromptsForExample({
        previousJapaneseSentence,
        japaneseSentence: selectedExampleText,
        koreanMeaning: form.krText,
      });
      setForm((currentForm) => ({
        ...currentForm,
        prompt: prompts.positivePrompt,
        negativePrompt: appendDefaultNegativePrompt(prompts.negativePrompt),
      }));
    } catch (error) {
      setPromptError(
        error instanceof Error ? error.message : 'SDXL 프롬프트 생성에 실패했습니다.',
      );
    } finally {
      setIsGeneratingPrompt(false);
    }
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

    let nextSkill: ExplorerWordSkill = {
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
    if (!selectedExampleText) {
      throw new Error('일본어 문장이 없습니다.');
    }

    const surface = selectedWord.surface.trim();
    const lemma = selectedWord.lemma.trim();
    if (!surface || !lemma) {
      throw new Error('단어 정보가 부족합니다.');
    }

    return fetchJapaneseWordKoreanMeaning({
      sentence: selectedExampleText,
      surface,
      lemma,
    });
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
    if (selectedExample?.id == null) {
      setAudioDeleteError('예문을 선택해 주세요.');
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
      const prompt = form.prompt.trim();
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
      const prompt = form.prompt.trim();
      const negativePrompt = form.negativePrompt.trim();
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

  const contextValue = {
    session: {
      authReady,
      isAdmin,
    },
    list,
    selectedExample,
    selectExample,
    detail: {
      form,
      isDirty,
      isSaving: isSavingExample,
      isDeleting: isDeletingExample,
      isTranslating,
      isGeneratingPrompt,
      saveError,
      saveMessage,
      deleteError,
      deleteMessage,
      translationError,
      promptError,
      canSave: canSaveExample,
      canDelete: canDeleteExample,
      setField: setFormField,
      save: saveExample,
      deleteSelected: deleteSelectedExample,
      translate: translateMeaning,
      generatePrompt,
    },
    words: {
      items: words,
      selectedWordId,
      selectedWord,
      isModalOpen: isWordModalOpen,
      isExtracting: isExtractingWords,
      extractionError,
      selectedWordCanSaveSkill,
      openWordModal,
      closeModal: () => setIsWordModalOpen(false),
      submitWord,
      deleteWord,
      fetchSelectedWordMeaning,
    },
    audio: {
      audios,
      isLoadingAudios,
      autoPlayKey: audioAutoPlayKey,
      deletingAudioId,
      audioListError,
      deleteError: audioDeleteError,
      errors: [
        audioDeleteError,
        audioListError,
      ].filter((message): message is string => Boolean(message)),
      saveMessage: audioSaveMessage,
      refreshSaved: refreshSavedAudios,
      deleteSaved: deleteSavedAudio,
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
      previewSrc: imagePreviewSrc,
      previewAlt: imagePreviewAlt,
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
  };

  return (
    <ExampleExplorerContext.Provider value={contextValue}>
      {children}
    </ExampleExplorerContext.Provider>
  );
}
