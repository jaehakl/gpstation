import { createContext, useContext } from 'react';
import type { ImageRecord } from '../../api/types';
import type { useImageList } from './hooks/useImageList';
import type {
  ImageExplorerForm,
  ImageExplorerGeneratedPreview,
  ImageExplorerSimilarState,
} from './types';

export type ImageExplorerContextValue = {
  session: {
    authReady: boolean;
    isAdmin: boolean;
  };
  list: ReturnType<typeof useImageList>;
  selectedImage: ImageRecord | null;
  selectImage: (image: ImageRecord) => void;
  detail: {
    form: ImageExplorerForm;
    isDirty: boolean;
    isGenerating: boolean;
    isSaving: boolean;
    isDeleting: boolean;
    generationError: string | null;
    saveError: string | null;
    saveMessage: string | null;
    deleteError: string | null;
    deleteMessage: string | null;
    generatedPreview: ImageExplorerGeneratedPreview | null;
    previewSrc: string | null;
    previewAlt: string;
    canGenerate: boolean;
    canSave: boolean;
    canDelete: boolean;
    saveDisabledReason: string | null;
    setField: <Field extends keyof ImageExplorerForm>(
      field: Field,
      value: ImageExplorerForm[Field],
    ) => void;
    generateImage: () => Promise<void>;
    save: () => Promise<void>;
    deleteImage: () => Promise<void>;
  };
  similar: ImageExplorerSimilarState;
};

export const ImageExplorerContext =
  createContext<ImageExplorerContextValue | null>(null);

export function useImageExplorer() {
  const context = useContext(ImageExplorerContext);

  if (!context) {
    throw new Error('useImageExplorer must be used within ImageExplorerProvider.');
  }

  return context;
}
