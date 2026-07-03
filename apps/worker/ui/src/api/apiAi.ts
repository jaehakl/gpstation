export const AI_API_URL = (process.env.NEXT_PUBLIC_AI_API_BASE_URL || 'http://localhost:8001').replace(
  /\/+$/,
  '',
);

export const VOICEVOX_API_URL = (
  process.env.NEXT_PUBLIC_VOICEVOX_API_BASE_URL || 'http://localhost:50021'
).replace(/\/+$/, '');

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE';
type QueryValue = string | number | boolean | null | undefined;
type QueryParams = Record<string, QueryValue>;
type RequestBody = unknown[] | Record<string, unknown> | URLSearchParams | string | number | boolean | null;

export type LlmRequest = {
  system_prompt: string;
  prompt: string;
  max_tokens?: number | null;
  temperature?: number | null;
};

export type LlmResponse = {
  answer: string;
};

export type SdxlT2IRequest = {
  prompts: string[];
  negative_prompts?: string[] | null;
  seeds?: Array<number | null> | null;
  format?: SdxlImageFormat;
  step?: number;
  cfg?: number;
  height?: number;
  width?: number;
  strength?: number;
  max_chunk_size?: number;
  seed_min?: number;
  seed_max?: number;
  sampler?: string;
  scheduler?: string;
  clip_skip?: number | null;
};

export type SdxlImageFormat = 'png' | 'jpg' | 'jpeg';
export type SdxlGeneratedImageFormat = 'png' | 'jpg';

export type GeneratedImage = {
  image_base64: string;
  format: string;
  seed: number;
};

export type SdxlT2IResponse = {
  images: GeneratedImage[];
  count: number;
};

export function getGeneratedImageFileMetadata(format: string | null | undefined): {
  extension: SdxlGeneratedImageFormat;
  format: SdxlGeneratedImageFormat;
  mimeType: 'image/png' | 'image/jpeg';
} {
  const normalizedFormat = format?.trim().toLowerCase();
  if (normalizedFormat === 'png') {
    return { extension: 'png', format: 'png', mimeType: 'image/png' };
  }
  return { extension: 'jpg', format: 'jpg', mimeType: 'image/jpeg' };
}

export type EmbeddingRequest = {
  text: string;
};

export type EmbeddingResponse = {
  embedding: number[];
  dimensions: number;
};

export type VoicevoxStyle = {
  id: number;
  name: string;
  type?: string;
};

export type VoicevoxSpeaker = {
  name: string;
  speaker_uuid: string;
  styles: VoicevoxStyle[];
  version?: string;
  policy?: string;
};

export type VoicevoxSpeakerInfo = {
  policy?: string;
  portrait?: string;
  style_infos?: Array<{
    id: number;
    icon?: string;
    portrait?: string | null;
    voice_samples?: string[];
  }>;
};

export type VoicevoxAudioQuery = Record<string, unknown>;
export type VoicevoxAccentPhrase = Record<string, unknown>;
export type VoicevoxPreset = Record<string, unknown>;
export type VoicevoxUserDictWord = Record<string, unknown>;

function buildUrl(baseUrl: string, path: string, query: QueryParams = {}) {
  const url = new URL(`${baseUrl}${path}`);

  Object.entries(query).forEach(([key, value]) => {
    if (value !== null && value !== undefined) {
      url.searchParams.set(key, String(value));
    }
  });

  return url.toString();
}

async function readErrorMessage(response: Response) {
  const fallback = `${response.status} ${response.statusText}`.trim();
  const text = await response.text();

  if (!text) {
    return fallback;
  }

  try {
    const data = JSON.parse(text) as {
      detail?: unknown;
      error?: unknown;
      message?: unknown;
    };
    const value = data.detail ?? data.error ?? data.message;

    if (typeof value === 'string') {
      return value;
    }

    return value === undefined ? text : JSON.stringify(value);
  } catch {
    return text;
  }
}

async function requestJson<T>(
  baseUrl: string,
  path: string,
  {
    method = 'GET',
    query,
    body,
    textResponse = false,
  }: {
    method?: HttpMethod;
    query?: QueryParams;
    body?: RequestBody;
    textResponse?: boolean;
  } = {},
): Promise<T> {
  const hasJsonBody = body !== undefined && !(body instanceof URLSearchParams);
  const response = await fetch(buildUrl(baseUrl, path, query), {
    method,
    headers: hasJsonBody ? { 'Content-Type': 'application/json' } : undefined,
    body: body === undefined ? undefined : hasJsonBody ? JSON.stringify(body) : body,
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  const text = await response.text();
  if (textResponse) {
    return text as T;
  }

  return text ? (JSON.parse(text) as T) : (undefined as T);
}

async function requestBlob(
  baseUrl: string,
  path: string,
  {
    method = 'POST',
    query,
    body,
  }: {
    method?: HttpMethod;
    query?: QueryParams;
    body?: RequestBody;
  } = {},
): Promise<Blob> {
  const hasJsonBody = body !== undefined && !(body instanceof URLSearchParams);
  const response = await fetch(buildUrl(baseUrl, path, query), {
    method,
    headers: hasJsonBody ? { 'Content-Type': 'application/json' } : undefined,
    body: body === undefined ? undefined : hasJsonBody ? JSON.stringify(body) : body,
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  return response.blob();
}

export const aiFastApi = {
  llm: (request: LlmRequest) =>
    requestJson<LlmResponse>(AI_API_URL, '/llm', { method: 'POST', body: request }),

  sdxlT2i: (request: SdxlT2IRequest) =>
    requestJson<SdxlT2IResponse>(AI_API_URL, '/sdxl/t2i', { method: 'POST', body: request }),

  embeddings: (request: EmbeddingRequest) =>
    requestJson<EmbeddingResponse>(AI_API_URL, '/embeddings', { method: 'POST', body: request }),
};

export const voicevoxApi = {
  audioQuery: (params: {
    text: string;
    speaker: number;
    enable_katakana_english?: boolean;
    core_version?: string;
  }) => requestJson<VoicevoxAudioQuery>(VOICEVOX_API_URL, '/audio_query', { method: 'POST', query: params }),

  audioQueryFromPreset: (params: {
    text: string;
    preset_id: number;
    enable_katakana_english?: boolean;
    core_version?: string;
  }) =>
    requestJson<VoicevoxAudioQuery>(VOICEVOX_API_URL, '/audio_query_from_preset', {
      method: 'POST',
      query: params,
    }),

  accentPhrases: (params: {
    text: string;
    speaker: number;
    is_kana?: boolean;
    enable_katakana_english?: boolean;
    core_version?: string;
  }) =>
    requestJson<VoicevoxAccentPhrase[]>(VOICEVOX_API_URL, '/accent_phrases', {
      method: 'POST',
      query: params,
    }),

  moraData: (accentPhrases: VoicevoxAccentPhrase[], params: { speaker: number; core_version?: string }) =>
    requestJson<VoicevoxAccentPhrase[]>(VOICEVOX_API_URL, '/mora_data', {
      method: 'POST',
      query: params,
      body: accentPhrases,
    }),

  moraLength: (accentPhrases: VoicevoxAccentPhrase[], params: { speaker: number; core_version?: string }) =>
    requestJson<VoicevoxAccentPhrase[]>(VOICEVOX_API_URL, '/mora_length', {
      method: 'POST',
      query: params,
      body: accentPhrases,
    }),

  moraPitch: (accentPhrases: VoicevoxAccentPhrase[], params: { speaker: number; core_version?: string }) =>
    requestJson<VoicevoxAccentPhrase[]>(VOICEVOX_API_URL, '/mora_pitch', {
      method: 'POST',
      query: params,
      body: accentPhrases,
    }),

  synthesis: (
    audioQuery: VoicevoxAudioQuery,
    params: {
      speaker: number;
      enable_interrogative_upspeak?: boolean;
      core_version?: string;
    },
  ) => requestBlob(VOICEVOX_API_URL, '/synthesis', { method: 'POST', query: params, body: audioQuery }),

  cancellableSynthesis: (
    audioQuery: VoicevoxAudioQuery,
    params: {
      speaker: number;
      enable_interrogative_upspeak?: boolean;
      core_version?: string;
    },
  ) =>
    requestBlob(VOICEVOX_API_URL, '/cancellable_synthesis', {
      method: 'POST',
      query: params,
      body: audioQuery,
    }),

  multiSynthesis: (
    audioQueries: VoicevoxAudioQuery[],
    params: {
      speaker: number;
      enable_interrogative_upspeak?: boolean;
      core_version?: string;
    },
  ) =>
    requestBlob(VOICEVOX_API_URL, '/multi_synthesis', {
      method: 'POST',
      query: params,
      body: audioQueries,
    }),

  singFrameAudioQuery: (request: Record<string, unknown>, params: { speaker: number; core_version?: string }) =>
    requestJson<Record<string, unknown>>(VOICEVOX_API_URL, '/sing_frame_audio_query', {
      method: 'POST',
      query: params,
      body: request,
    }),

  singFrameF0: (request: Record<string, unknown>, params: { speaker: number; core_version?: string }) =>
    requestJson<Record<string, unknown>>(VOICEVOX_API_URL, '/sing_frame_f0', {
      method: 'POST',
      query: params,
      body: request,
    }),

  singFrameVolume: (request: Record<string, unknown>, params: { speaker: number; core_version?: string }) =>
    requestJson<Record<string, unknown>>(VOICEVOX_API_URL, '/sing_frame_volume', {
      method: 'POST',
      query: params,
      body: request,
    }),

  frameSynthesis: (request: Record<string, unknown>, params: { speaker: number; core_version?: string }) =>
    requestBlob(VOICEVOX_API_URL, '/frame_synthesis', {
      method: 'POST',
      query: params,
      body: request,
    }),

  connectWaves: (waves: unknown[]) =>
    requestBlob(VOICEVOX_API_URL, '/connect_waves', { method: 'POST', body: waves }),

  validateKana: (text: string) =>
    requestJson<boolean>(VOICEVOX_API_URL, '/validate_kana', { method: 'POST', query: { text } }),

  initializeSpeaker: (params: { speaker: number; skip_reinit?: boolean; core_version?: string }) =>
    requestJson<void>(VOICEVOX_API_URL, '/initialize_speaker', { method: 'POST', query: params }),

  isInitializedSpeaker: (params: { speaker: number; core_version?: string }) =>
    requestJson<boolean>(VOICEVOX_API_URL, '/is_initialized_speaker', { query: params }),

  supportedDevices: (params: { core_version?: string } = {}) =>
    requestJson<Record<string, unknown>>(VOICEVOX_API_URL, '/supported_devices', { query: params }),

  morphableTargets: (request: Record<string, unknown>, params: { core_version?: string } = {}) =>
    requestJson<Record<string, unknown>>(VOICEVOX_API_URL, '/morphable_targets', {
      method: 'POST',
      query: params,
      body: request,
    }),

  synthesisMorphing: (
    audioQuery: VoicevoxAudioQuery,
    params: {
      base_speaker: number;
      target_speaker: number;
      morph_rate: number;
      enable_interrogative_upspeak?: boolean;
      core_version?: string;
    },
  ) =>
    requestBlob(VOICEVOX_API_URL, '/synthesis_morphing', {
      method: 'POST',
      query: params,
      body: audioQuery,
    }),

  presets: () => requestJson<VoicevoxPreset[]>(VOICEVOX_API_URL, '/presets'),

  addPreset: (preset: VoicevoxPreset) =>
    requestJson<number>(VOICEVOX_API_URL, '/add_preset', { method: 'POST', body: preset }),

  updatePreset: (preset: VoicevoxPreset) =>
    requestJson<number>(VOICEVOX_API_URL, '/update_preset', { method: 'POST', body: preset }),

  deletePreset: (id: number) =>
    requestJson<void>(VOICEVOX_API_URL, '/delete_preset', { method: 'POST', query: { id } }),

  speakers: (params: { core_version?: string } = {}) =>
    requestJson<VoicevoxSpeaker[]>(VOICEVOX_API_URL, '/speakers', { query: params }),

  speakerInfo: (params: {
    speaker_uuid: string;
    resource_format?: string;
    core_version?: string;
  }) => requestJson<VoicevoxSpeakerInfo>(VOICEVOX_API_URL, '/speaker_info', { query: params }),

  singers: (params: { core_version?: string } = {}) =>
    requestJson<VoicevoxSpeaker[]>(VOICEVOX_API_URL, '/singers', { query: params }),

  singerInfo: (params: {
    speaker_uuid: string;
    resource_format?: string;
    core_version?: string;
  }) => requestJson<Record<string, unknown>>(VOICEVOX_API_URL, '/singer_info', { query: params }),

  downloadableLibraries: () =>
    requestJson<Record<string, unknown>[]>(VOICEVOX_API_URL, '/downloadable_libraries'),

  installedLibraries: () =>
    requestJson<Record<string, unknown>[]>(VOICEVOX_API_URL, '/installed_libraries'),

  installLibrary: (libraryUuid: string) =>
    requestJson<void>(VOICEVOX_API_URL, `/install_library/${encodeURIComponent(libraryUuid)}`, {
      method: 'POST',
    }),

  uninstallLibrary: (libraryUuid: string) =>
    requestJson<void>(VOICEVOX_API_URL, `/uninstall_library/${encodeURIComponent(libraryUuid)}`, {
      method: 'POST',
    }),

  userDict: () => requestJson<Record<string, VoicevoxUserDictWord>>(VOICEVOX_API_URL, '/user_dict'),

  addUserDictWord: (params: {
    surface: string;
    pronunciation: string;
    accent_type: number;
    word_type?: string;
    priority?: number;
  }) => requestJson<string>(VOICEVOX_API_URL, '/user_dict_word', { method: 'POST', query: params }),

  updateUserDictWord: (
    wordUuid: string,
    params: {
      surface: string;
      pronunciation: string;
      accent_type: number;
      word_type?: string;
      priority?: number;
    },
  ) =>
    requestJson<void>(VOICEVOX_API_URL, `/user_dict_word/${encodeURIComponent(wordUuid)}`, {
      method: 'PUT',
      query: params,
    }),

  deleteUserDictWord: (wordUuid: string) =>
    requestJson<void>(VOICEVOX_API_URL, `/user_dict_word/${encodeURIComponent(wordUuid)}`, {
      method: 'DELETE',
    }),

  importUserDict: (userDict: Record<string, VoicevoxUserDictWord>, override: boolean) =>
    requestJson<void>(VOICEVOX_API_URL, '/import_user_dict', {
      method: 'POST',
      query: { override },
      body: userDict,
    }),

  version: () => requestJson<string>(VOICEVOX_API_URL, '/version'),

  coreVersions: () => requestJson<string[]>(VOICEVOX_API_URL, '/core_versions'),

  engineManifest: () => requestJson<Record<string, unknown>>(VOICEVOX_API_URL, '/engine_manifest'),

  getSetting: () => requestJson<Record<string, unknown>>(VOICEVOX_API_URL, '/setting'),

  updateSetting: (setting: URLSearchParams | Record<string, string | number | boolean>) =>
    requestJson<void>(VOICEVOX_API_URL, '/setting', {
      method: 'POST',
      body:
        setting instanceof URLSearchParams
          ? setting
          : new URLSearchParams(Object.entries(setting).map(([key, value]) => [key, String(value)])),
    }),

  root: () => requestJson<string>(VOICEVOX_API_URL, '/', { textResponse: true }),
};
