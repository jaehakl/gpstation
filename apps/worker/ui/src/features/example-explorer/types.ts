import type { SdxlGeneratedImageFormat } from '../../api/apiAi';

export type ExampleExplorerSortField =
  | 'id'
  | 'jp_text'
  | 'kr_text'
  | 'audios'
  | 'jp_words'
  | 'similar_prompt_image_score'
  | 'similar_context_text_example_score'
  | 'similar_text_context_example_score';
export type ExampleExplorerSortDirection = 'asc' | 'desc';

export type ExampleExplorerForm = {
  krText: string;
  prompt: string;
  negativePrompt: string;
};

export type ExplorerWordSkill = {
  id?: number | null;
  userId?: string | null;
  wordId: number;
  reading: number;
  listening: number;
  speaking: number;
  createdAt?: string | null;
  updatedAt?: string | null;
};

export type ExplorerWord = {
  id: string;
  wordId: number | null;
  lemmaId: number | null;
  surface: string;
  lemma: string;
  jpPron: string;
  krMean: string;
  userWordSkill: ExplorerWordSkill | null;
};

export type ExplorerAudio = {
  id: string;
  speaker: string;
  tone?: string;
  filename: string;
  createdAt: string;
  src?: string | null;
};

export type ExplorerGeneratedImagePreview = {
  blob: Blob;
  prompt: string;
  negativePrompt: string;
  seed: number;
  format: SdxlGeneratedImageFormat;
  extension: SdxlGeneratedImageFormat;
  mimeType: 'image/png' | 'image/jpeg';
  url: string;
};

export type ExplorerRecommendedImage = {
  id: number;
  title: string;
  prompt: string;
  negativePrompt: string;
  score: number;
  scoreLabel: string;
  src: string | null;
};

export type ExplorerAudioState = {
  audios: ExplorerAudio[];
  isLoadingAudios: boolean;
  autoPlayKey: number;
  deletingAudioId: string | null;
  audioListError: string | null;
  deleteError: string | null;
  errors: string[];
  saveMessage: string | null;
  refreshSaved: () => Promise<void>;
  deleteSaved: (audioId: string) => Promise<void>;
};

export type ExplorerImageState = {
  isGeneratingImage: boolean;
  isRecommending: boolean;
  isSaving: boolean;
  imageGenerationError: string | null;
  recommendationError: string | null;
  saveError: string | null;
  saveMessage: string | null;
  generatedPreview: ExplorerGeneratedImagePreview | null;
  recommendedImage: ExplorerRecommendedImage | null;
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
