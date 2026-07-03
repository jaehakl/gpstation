import { createContext, useContext } from 'react';
import type { SdxlGeneratedImageFormat } from '../../api/apiAi';
import type { ExampleRecord } from '../../api/types';
import type { WordInputModalValue } from '../../components/WordInputModal';
import type { EditorAudio, EditorWord, ExampleDraft } from './types';

export type PendingExampleSave = {
  jpText: string;
  krText: string;
  sourceText: string;
  prompt: string;
  negativePrompt: string;
  textEmbedding: number[];
  promptEmbedding: number[];
  candidate: {
    id: number;
    score: number;
    example: ExampleRecord;
  } | null;
};

export type GeneratedImagePreview = {
  blob: Blob;
  prompt: string;
  negativePrompt: string;
  seed: number;
  format: SdxlGeneratedImageFormat;
  extension: SdxlGeneratedImageFormat;
  mimeType: 'image/png' | 'image/jpeg';
  url: string;
};

export type RecommendedImage = {
  id: number;
  title: string;
  prompt: string;
  negativePrompt: string;
  score: number;
  scoreLabel: string;
  src: string | null;
};

export type LowSimilarityExampleCandidate = {
  id: number;
  jpText: string;
  similarityScore: number | null;
  targetId: number | null;
  targetJpText: string | null;
};

export type LowExampleCountWordCandidate = {
  id: number;
  lemma: string;
  krMean: string;
  exampleCount: number;
};

export type ExampleEditorContextValue = {
  session: {
    authReady: boolean;
    isAdmin: boolean;
  };
  draft: {
    value: ExampleDraft;
    set: (draft: ExampleDraft) => void;
    setField: <Field extends keyof ExampleDraft>(
      field: Field,
      value: ExampleDraft[Field],
    ) => void;
  };
  sentence: {
    isGenerating: boolean;
    generationError: string | null;
    isTranslating: boolean;
    translationError: string | null;
    isPickingRandomExample: boolean;
    randomExampleError: string | null;
    isPickingRandomWord: boolean;
    randomWordError: string | null;
    isLoadingLowExampleCountWords: boolean;
    lowExampleCountWordError: string | null;
    lowExampleCountWords: LowExampleCountWordCandidate[];
    isLowExampleCountWordPickerOpen: boolean;
    deletingLowExampleCountWordId: number | null;
    isLoadingLowSimilarityExamples: boolean;
    lowSimilarityExampleError: string | null;
    lowSimilarityExamples: LowSimilarityExampleCandidate[];
    isLowSimilarityPickerOpen: boolean;
    isGeneratingPrompt: boolean;
    promptError: string | null;
    cannotGeneratePrompt: boolean;
    generate: () => Promise<void>;
    translate: () => Promise<void>;
    pickRandomExample: () => Promise<void>;
    pickRandomWord: () => Promise<void>;
    openLowExampleCountWordPicker: () => Promise<void>;
    closeLowExampleCountWordPicker: () => void;
    selectLowExampleCountWord: (candidate: LowExampleCountWordCandidate) => void;
    deleteLowExampleCountWord: (candidateId: number) => Promise<void>;
    openLowSimilarityPicker: () => Promise<void>;
    closeLowSimilarityPicker: () => void;
    selectLowSimilarityExample: (candidate: LowSimilarityExampleCandidate) => void;
    generatePrompt: () => Promise<void>;
  };
  words: {
    items: EditorWord[];
    selectedWordId: string | null;
    selectedWord: EditorWord | null;
    isModalOpen: boolean;
    isExtracting: boolean;
    extractionError: string | null;
    cannotExtract: boolean;
    selectedWordCanSaveSkill: boolean;
    extract: () => Promise<void>;
    openNewWordModal: () => void;
    openWordModal: (wordId: string) => void;
    closeModal: () => void;
    submitWord: (word: WordInputModalValue) => Promise<void>;
    deleteWord: (wordId: number) => Promise<void>;
    fetchSelectedWordMeaning: () => Promise<string>;
  };
  image: {
    isGeneratingImage: boolean;
    isRecommending: boolean;
    isSaving: boolean;
    imageGenerationError: string | null;
    recommendationError: string | null;
    saveError: string | null;
    saveMessage: string | null;
    generatedPreview: GeneratedImagePreview | null;
    recommendedImage: RecommendedImage | null;
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
  audio: {
    audios: EditorAudio[];
    isLoadingAudios: boolean;
    autoGenerateRequestKey: number;
    deletingAudioId: string | null;
    audioListError: string | null;
    deleteError: string | null;
    saveMessage: string | null;
    errors: string[];
    refreshSaved: () => Promise<void>;
    deleteSaved: (audioId: string) => Promise<void>;
  };
  save: {
    pending: PendingExampleSave | null;
    savedExampleId: number | null;
    isPreparing: boolean;
    isConfirming: boolean;
    isSaving: boolean;
    canSave: boolean;
    panelError: string | null;
    modalError: string | null;
    prepare: () => Promise<void>;
    confirm: (exampleId?: number) => Promise<void>;
    closeModal: () => void;
  };
  autoFlow: {
    isRunning: boolean;
    step: string | null;
    error: string | null;
    cannotRun: boolean;
    run: () => Promise<void>;
  };
};

export const ExampleEditorContext = createContext<ExampleEditorContextValue | null>(null);

export function useExampleEditor() {
  const context = useContext(ExampleEditorContext);

  if (!context) {
    throw new Error('useExampleEditor must be used within ExampleEditorProvider.');
  }

  return context;
}
