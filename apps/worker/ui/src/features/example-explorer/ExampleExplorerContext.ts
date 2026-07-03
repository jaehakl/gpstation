import { createContext, useContext } from 'react';
import type { ExampleSortSimilarRecord } from '../../api/types';
import type { WordInputModalValue } from '../../components/WordInputModal';
import type { useExampleList } from './hooks/useExampleList';
import type {
  ExampleExplorerForm,
  ExplorerAudioState,
  ExplorerImageState,
  ExplorerWord,
} from './types';

export type ExampleExplorerContextValue = {
  session: {
    authReady: boolean;
    isAdmin: boolean;
  };
  list: ReturnType<typeof useExampleList>;
  selectedExample: ExampleSortSimilarRecord | null;
  selectExample: (example: ExampleSortSimilarRecord) => void;
  detail: {
    form: ExampleExplorerForm;
    isDirty: boolean;
    isSaving: boolean;
    isDeleting: boolean;
    isTranslating: boolean;
    isGeneratingPrompt: boolean;
    saveError: string | null;
    saveMessage: string | null;
    deleteError: string | null;
    deleteMessage: string | null;
    translationError: string | null;
    promptError: string | null;
    canSave: boolean;
    canDelete: boolean;
    setField: <Field extends keyof ExampleExplorerForm>(
      field: Field,
      value: ExampleExplorerForm[Field],
    ) => void;
    save: () => Promise<void>;
    deleteSelected: () => Promise<void>;
    translate: () => Promise<void>;
    generatePrompt: () => Promise<void>;
  };
  words: {
    items: ExplorerWord[];
    selectedWordId: string | null;
    selectedWord: ExplorerWord | null;
    isModalOpen: boolean;
    isExtracting: boolean;
    extractionError: string | null;
    selectedWordCanSaveSkill: boolean;
    openWordModal: (wordId: string) => void;
    closeModal: () => void;
    submitWord: (word: WordInputModalValue) => Promise<void>;
    deleteWord: (wordId: number) => Promise<void>;
    fetchSelectedWordMeaning: () => Promise<string>;
  };
  audio: ExplorerAudioState;
  image: ExplorerImageState;
};

export const ExampleExplorerContext =
  createContext<ExampleExplorerContextValue | null>(null);

export function useExampleExplorer() {
  const context = useContext(ExampleExplorerContext);

  if (!context) {
    throw new Error('useExampleExplorer must be used within ExampleExplorerProvider.');
  }

  return context;
}
