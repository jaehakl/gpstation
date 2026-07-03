import type { SdxlGeneratedImageFormat } from '../../api/apiAi';
import type { ExampleRecord, ImageRecord } from '../../api/types';

export type ImageExplorerSortField =
  | 'id'
  | 'created_at'
  | 'updated_at'
  | 'prompt'
  | 'negative_prompt';

export type ImageExplorerSortDirection = 'asc' | 'desc';

export type ImageExplorerForm = {
  prompt: string;
  negativePrompt: string;
};

export type ImageExplorerGeneratedPreview = {
  blob: Blob;
  prompt: string;
  negativePrompt: string;
  seed: number;
  format: SdxlGeneratedImageFormat;
  extension: SdxlGeneratedImageFormat;
  mimeType: 'image/png' | 'image/jpeg';
  url: string;
};

export type ImageExplorerSimilarState = {
  images: ImageRecord[];
  examples: ExampleRecord[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
};
