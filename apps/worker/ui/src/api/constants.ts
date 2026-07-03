import type { SdxlT2IRequest } from './apiAi';

export const SDXL_IMAGE_GENERATION_PARAMS = {
  step: 30,
  cfg: 5.0,
  height: 832,
  width: 1216,
  strength: 1.0,
  max_chunk_size: 1,
  seed_min: 0,
  seed_max: 2147483647,
  sampler: 'euler_a',
  scheduler: '',
  clip_skip: null,
  format: 'jpg',
} satisfies Omit<SdxlT2IRequest, 'prompts' | 'negative_prompts' | 'seeds'>;

export const SDXL_IMAGE_ASPECT_RATIO =
  `${SDXL_IMAGE_GENERATION_PARAMS.width} / ${SDXL_IMAGE_GENERATION_PARAMS.height}`;
