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
import type { ExampleRecord, ImageRecord } from '../../api/types';
import { useAuthStore } from '../../stores/authStore';
import { ImageExplorerContext } from './ImageExplorerContext';
import { useImageList } from './hooks/useImageList';
import type {
  ImageExplorerForm,
  ImageExplorerGeneratedPreview,
} from './types';

const SIMILAR_RESULT_LIMIT = 12;

type ImageExplorerProviderProps = {
  children: ReactNode;
};

function createFormFromImage(image: ImageRecord | null): ImageExplorerForm {
  return {
    prompt: image?.prompt ?? '',
    negativePrompt: image?.negative_prompt ?? '',
  };
}

export function ImageExplorerProvider({ children }: ImageExplorerProviderProps) {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const isAdmin = user?.roles.includes('admin') ?? false;
  const list = useImageList();
  const [selectedImage, setSelectedImage] = useState<ImageRecord | null>(null);
  const [form, setForm] = useState<ImageExplorerForm>(createFormFromImage(null));
  const [generatedPreview, setGeneratedPreview] =
    useState<ImageExplorerGeneratedPreview | null>(null);
  const [isGeneratingImage, setIsGeneratingImage] = useState(false);
  const [isSavingImage, setIsSavingImage] = useState(false);
  const [isDeletingImage, setIsDeletingImage] = useState(false);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteMessage, setDeleteMessage] = useState<string | null>(null);
  const [similarImages, setSimilarImages] = useState<ImageRecord[]>([]);
  const [similarExamples, setSimilarExamples] = useState<ExampleRecord[]>([]);
  const [isLoadingSimilar, setIsLoadingSimilar] = useState(false);
  const [similarError, setSimilarError] = useState<string | null>(null);
  const generatedPreviewUrlRef = useRef<string | null>(null);
  const similarRequestKeyRef = useRef(0);

  const selectedImageId = selectedImage?.id ?? null;
  const prompt = form.prompt.trim();
  const negativePrompt = form.negativePrompt.trim();
  const isDirty = selectedImage
    ? form.prompt !== (selectedImage.prompt ?? '')
      || form.negativePrompt !== (selectedImage.negative_prompt ?? '')
    : false;
  const isGeneratedPreviewCurrent =
    generatedPreview != null
    && generatedPreview.prompt === prompt
    && generatedPreview.negativePrompt === negativePrompt;
  const canGenerate =
    selectedImageId != null && !isGeneratingImage && !isSavingImage && Boolean(prompt);
  const canSave =
    selectedImageId != null
    && authReady
    && isAdmin
    && !isGeneratingImage
    && !isSavingImage
    && isGeneratedPreviewCurrent;
  const canDelete =
    selectedImageId != null
    && authReady
    && isAdmin
    && !isGeneratingImage
    && !isSavingImage
    && !isDeletingImage;
  const saveDisabledReason =
    selectedImageId == null
      ? '이미지를 선택해 주세요.'
      : !authReady
        ? '사용자 정보를 확인 중입니다.'
        : !isAdmin
          ? 'admin 권한이 있어야 이미지를 저장할 수 있습니다.'
          : !generatedPreview
            ? '이미지를 먼저 생성해 주세요.'
            : !isGeneratedPreviewCurrent
              ? '마지막 이미지 생성 후 prompt가 변경되었습니다.'
              : null;
  const previewSrc = generatedPreview?.url ?? selectedImage?.object_key ?? null;
  const previewAlt = generatedPreview
    ? `generated image seed ${generatedPreview.seed}`
    : selectedImage?.id != null
      ? `image-${selectedImage.id}`
      : '선택된 이미지';

  const clearGeneratedPreview = useCallback(() => {
    if (generatedPreviewUrlRef.current) {
      URL.revokeObjectURL(generatedPreviewUrlRef.current);
      generatedPreviewUrlRef.current = null;
    }
    setGeneratedPreview(null);
  }, []);

  const clearSelectedImage = useCallback(() => {
    setSelectedImage(null);
    setForm(createFormFromImage(null));
    clearGeneratedPreview();
    setGenerationError(null);
    setSaveError(null);
    setSaveMessage(null);
    setDeleteError(null);
    setDeleteMessage(null);
  }, [clearGeneratedPreview]);

  const selectImage = (image: ImageRecord) => {
    setSelectedImage(image);
    setForm(createFormFromImage(image));
    clearGeneratedPreview();
    setGenerationError(null);
    setSaveError(null);
    setSaveMessage(null);
    setDeleteError(null);
    setDeleteMessage(null);
  };

  const loadSimilar = useCallback(async () => {
    const imageId = selectedImageId;
    const requestKey = similarRequestKeyRef.current + 1;
    similarRequestKeyRef.current = requestKey;

    if (imageId == null) {
      setSimilarImages([]);
      setSimilarExamples([]);
      setSimilarError(null);
      setIsLoadingSimilar(false);
      return;
    }

    setIsLoadingSimilar(true);
    setSimilarError(null);

    try {
      const response = await dbTables.Image.findSimilarByImage(
        imageId,
        SIMILAR_RESULT_LIMIT,
      );
      const imageRows = response.similar_image_ids.length
        ? await dbTables.Image.listRows({
            offset: 0,
            limit: response.similar_image_ids.length,
            selected_ids: response.similar_image_ids,
            search_text: null,
            text_filter: {},
            filter: {},
            sort: null,
          })
        : { total: 0, items: [] };
      const exampleRows = response.similar_example_ids.length
        ? await dbTables.Example.listRows({
            offset: 0,
            limit: response.similar_example_ids.length,
            selected_ids: response.similar_example_ids,
            search_text: null,
            text_filter: {},
            filter: {},
            sort: null,
          })
        : { total: 0, items: [] };

      if (similarRequestKeyRef.current !== requestKey) {
        return;
      }

      const imagesById = new Map(
        imageRows.items
          .filter((image): image is ImageRecord & { id: number } => image.id != null)
          .map((image) => [image.id, image]),
      );
      const examplesById = new Map(
        exampleRows.items
          .filter((example): example is ExampleRecord & { id: number } => example.id != null)
          .map((example) => [example.id, example]),
      );

      const nextSimilarImages: ImageRecord[] = [];
      response.similar_image_ids.forEach((similarImageId) => {
        const image = imagesById.get(similarImageId);
        if (image) {
          nextSimilarImages.push(image);
        }
      });

      const nextSimilarExamples: ExampleRecord[] = [];
      response.similar_example_ids.forEach((exampleId) => {
        const example = examplesById.get(exampleId);
        if (example) {
          nextSimilarExamples.push(example);
        }
      });

      setSimilarImages(nextSimilarImages);
      setSimilarExamples(nextSimilarExamples);
    } catch (similarLoadError) {
      if (similarRequestKeyRef.current === requestKey) {
        setSimilarImages([]);
        setSimilarExamples([]);
        setSimilarError(
          similarLoadError instanceof Error
            ? similarLoadError.message
            : '유사 항목을 불러오지 못했습니다.',
        );
      }
    } finally {
      if (similarRequestKeyRef.current === requestKey) {
        setIsLoadingSimilar(false);
      }
    }
  }, [selectedImageId]);

  useEffect(() => {
    return () => {
      if (generatedPreviewUrlRef.current) {
        URL.revokeObjectURL(generatedPreviewUrlRef.current);
      }
    };
  }, []);

  useEffect(() => {
    queueMicrotask(() => {
      void loadSimilar();
    });
  }, [loadSimilar]);

  const setFormField = <Field extends keyof ImageExplorerForm>(
    field: Field,
    value: ImageExplorerForm[Field],
  ) => {
    setForm((currentForm) => ({
      ...currentForm,
      [field]: value,
    }));
    setSaveMessage(null);
    setSaveError(null);
  };

  const generateImage = async () => {
    if (!canGenerate) {
      return;
    }

    setIsGeneratingImage(true);
    setGenerationError(null);
    setSaveError(null);
    setSaveMessage(null);

    try {
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

      clearGeneratedPreview();
      generatedPreviewUrlRef.current = url;
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
    } catch (imageGenerationError) {
      setGenerationError(
        imageGenerationError instanceof Error
          ? imageGenerationError.message
          : '이미지 생성에 실패했습니다.',
      );
    } finally {
      setIsGeneratingImage(false);
    }
  };

  const saveImage = async () => {
    if (!selectedImage?.id || !generatedPreview || isSavingImage) {
      return;
    }

    const imageId = selectedImage.id;
    const currentPrompt = form.prompt.trim();
    const currentNegativePrompt = form.negativePrompt.trim();
    if (
      generatedPreview.prompt !== currentPrompt
      || generatedPreview.negativePrompt !== currentNegativePrompt
    ) {
      setSaveError('마지막 이미지 생성 후 prompt가 변경되었습니다.');
      return;
    }
    if (!authReady) {
      setSaveError('사용자 정보를 확인 중입니다.');
      return;
    }
    if (!isAdmin) {
      setSaveError('admin 권한이 있어야 이미지를 저장할 수 있습니다.');
      return;
    }

    setIsSavingImage(true);
    setSaveError(null);
    setSaveMessage(null);

    try {
      const { embedding: promptEmbedding } = await aiFastApi.embeddings({
        text: currentPrompt,
      });
      const file = new File(
        [generatedPreview.blob],
        `sdxl-${generatedPreview.seed}-${Date.now()}.${generatedPreview.extension}`,
        { type: generatedPreview.blob.type || generatedPreview.mimeType },
      );
      await dbTables.Image.upsertFormRow(
        {
          id: imageId,
          prompt: currentPrompt,
          negative_prompt: currentNegativePrompt || null,
          prompt_embedding: promptEmbedding,
        },
        { object_key: file },
      );

      const response = await dbTables.Image.listRows({
        offset: 0,
        limit: 1,
        selected_ids: [imageId],
        search_text: null,
        text_filter: {},
        filter: {},
        sort: null,
      });
      const updatedImage =
        response.items.find((image) => image.id === imageId)
        ?? response.items[0]
        ?? null;

      if (!updatedImage) {
        throw new Error('저장된 이미지 정보를 다시 불러오지 못했습니다.');
      }

      setSelectedImage(updatedImage);
      setForm(createFormFromImage(updatedImage));
      list.updateListItem(updatedImage);
      clearGeneratedPreview();
      setSaveMessage('이미지를 저장했습니다.');
      void list.refresh();
      void loadSimilar();
    } catch (imageSaveError) {
      setSaveError(
        imageSaveError instanceof Error
          ? imageSaveError.message
          : '이미지를 저장하지 못했습니다.',
      );
    } finally {
      setIsSavingImage(false);
    }
  };

  const deleteImage = async () => {
    if (!selectedImage?.id || isDeletingImage) {
      return;
    }
    if (!authReady) {
      setDeleteError('사용자 정보를 확인 중입니다.');
      return;
    }
    if (!isAdmin) {
      setDeleteError('admin 권한이 있어야 이미지를 삭제할 수 있습니다.');
      return;
    }

    const imageId = selectedImage.id;
    setIsDeletingImage(true);
    setDeleteError(null);
    setDeleteMessage(null);

    try {
      await dbTables.Image.deleteRows([imageId]);
      clearSelectedImage();
      setDeleteMessage('이미지를 삭제했습니다.');
      await list.refresh();
    } catch (imageDeleteError) {
      setDeleteError(
        imageDeleteError instanceof Error
          ? imageDeleteError.message
          : '이미지를 삭제하지 못했습니다.',
      );
    } finally {
      setIsDeletingImage(false);
    }
  };

  const contextValue = {
    session: {
      authReady,
      isAdmin,
    },
    list,
    selectedImage,
    selectImage,
    detail: {
      form,
      isDirty,
      isGenerating: isGeneratingImage,
      isSaving: isSavingImage,
      isDeleting: isDeletingImage,
      generationError,
      saveError,
      saveMessage,
      deleteError,
      deleteMessage,
      generatedPreview,
      previewSrc,
      previewAlt,
      canGenerate,
      canSave,
      canDelete,
      saveDisabledReason,
      setField: setFormField,
      generateImage,
      save: saveImage,
      deleteImage,
    },
    similar: {
      images: similarImages,
      examples: similarExamples,
      isLoading: isLoadingSimilar,
      error: similarError,
      refresh: loadSimilar,
    },
  };

  return (
    <ImageExplorerContext.Provider value={contextValue}>
      {children}
    </ImageExplorerContext.Provider>
  );
}
