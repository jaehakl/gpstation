// YOU MUST OPEN ALL FRONTEND SOURCE FILES with UTF-8 ENCODING to READ KOREAN CHARACTERS CORRECTLY.

import { API_URL, request } from './http';
import type {
  AnalyzeJapaneseTextResponse,
  AnalyzeJapaneseTextSkills,
  AudioRecord,
  ErrorReportRecord,
  ExampleContextPlayResponse,
  ExampleRecord,
  ExampleSortSimilarRecord,
  GetListRequest,
  GetListResponse,
  ImagePromptSimilarityResponse,
  ImageRecord,
  JpWordRecord,
  SimilarityResult,
  SyncExampleJpWordsRequest,
  SyncExampleJpWordsResponse,
  TemporaryAutoFlowSeedResponse,
  UpsertResponse,
  UserData,
  UserJpWordSkillRecord,
  UserTextRecord,
} from './types';

export { API_URL };

export function startGoogleLogin() {
  const returnTo = window.location.href;
  window.location.href = `${API_URL}/auth/google/start?return_to=${encodeURIComponent(returnTo)}`;
}

export async function logout() {
  await request<{ ok: true }>('post', '/auth/logout');
}

function buildUpsertFormData(
  payload: unknown,
  files: Record<string, File | null | undefined> = {},
) {
  const formData = new FormData();
  formData.append('payload', JSON.stringify(payload));

  Object.entries(files).forEach(([field, file]) => {
    if (file) {
      formData.append(field, file, file.name);
    }
  });

  return formData;
}

export const dbTables = {
  User: {
    label: '사용자',
    columns: {
      id: { label: 'ID', type: 'id' },
      email: { label: '이메일', type: 'text' },
      display_name: { label: '이름', type: 'text' },
      picture_url: { label: '프로필 이미지', type: 'text' },
      is_active: { label: '활성', type: 'boolean' },
      roles: { label: '권한', type: 'list' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      updated_at: { label: '수정일', type: 'datetime', readOnly: true },
    },
    fetchMe: async () => {
      try {
        return await request<UserData>('get', '/auth/me');
      } catch {
        return null;
      }
    },
    getAllUsersAdmin: (limit: number, offset: number) =>
      request<UserData[]>(
        'get',
        `/user_admin/get_all_users/${encodeURIComponent(String(limit))}/${encodeURIComponent(String(offset))}`,
      ),
    deleteUserAdmin: (id: string) =>
      request<boolean>('get', `/user_admin/delete/${encodeURIComponent(id)}`),
    getUserSummaryAdmin: (userId: string) =>
      request<UserData | null>('get', `/user_data/summary/admin/${encodeURIComponent(userId)}`),
    getUserSummaryUser: () =>
      request<UserData | null>('get', '/user_data/summary/user'),
  },

  Example: {
    label: '예문',
    columns: {
      id: { label: 'ID', type: 'id' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      updated_at: { label: '수정일', type: 'datetime', readOnly: true },
      jp_text: { label: '일본어', type: 'text', required: true },
      kr_text: { label: '한국어', type: 'text', required: true },
      context: { label: '기존 일본어 문장', type: 'text' },
      prompt: { label: '프롬프트', type: 'text' },
      negative_prompt: { label: '네거티브 프롬프트', type: 'text' },
      jp_words: { label: '단어', type: 'list-fk', targetTable: 'JpWord', linkType: 'secondary' },
      audios: { label: '오디오', type: 'list-fk', targetTable: 'Audio', linkType: 'children', readOnly: true },
      error_reports: { label: '오류 제보', type: 'list-fk', targetTable: 'ErrorReport', linkType: 'children', readOnly: true },
    },
    listRows: (listRequest: GetListRequest) =>
      request<GetListResponse<ExampleRecord>>('post', '/example/list', listRequest),
    contextPlay: (
      exampleId: number,
      skills?: AnalyzeJapaneseTextSkills,
    ) =>
      request<ExampleContextPlayResponse>('post', '/example/context-play', {
        example_id: exampleId,
        ...(skills ? { skills } : {}),
      }),
    upsertRow: (items: ExampleRecord[]) =>
      request<UpsertResponse[]>('post', '/example/upsert', items),
    deleteRows: (ids: number[]) =>
      request<null>('delete', '/example/', ids).then(() => undefined),
  },

  JpWord: {
    label: '일본어 단어',
    columns: {
      id: { label: 'ID', type: 'id' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      updated_at: { label: '수정일', type: 'datetime', readOnly: true },
      lemma_id: { label: 'Lemma ID', type: 'number', required: true },
      lemma: { label: 'Lemma', type: 'text', required: true },
      kr_mean: { label: '뜻', type: 'text', required: true },
      examples: { label: '예문', type: 'list-fk', targetTable: 'Example', linkType: 'secondary' },
      user_word_skills: { label: '숙련도', type: 'list-fk', targetTable: 'UserJpWordSkill', linkType: 'children', readOnly: true },
    },
    listRows: (listRequest: GetListRequest) =>
      request<GetListResponse<JpWordRecord>>('post', '/jp_word/list', listRequest),
    listRowsWithProns: (listRequest: GetListRequest) =>
      request<GetListResponse<JpWordRecord>>('post', '/jp_word/list-with-prons', listRequest),
    upsertRow: (items: JpWordRecord[]) =>
      request<UpsertResponse[]>('post', '/jp_word/upsert', items),
    deleteRows: (ids: number[]) =>
      request<null>('delete', '/jp_word/', ids).then(() => undefined),
    analyzeJapaneseText: (
      text: string,
      skills?: AnalyzeJapaneseTextSkills,
    ) =>
      request<AnalyzeJapaneseTextResponse>('post', '/text/analyze/jp', {
        text,
        ...(skills ? { skills } : {}),
      }),
  },

  Image: {
    label: '이미지',
    columns: {
      id: { label: 'ID', type: 'id' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      updated_at: { label: '수정일', type: 'datetime', readOnly: true },
      prompt: { label: '프롬프트', type: 'text' },
      negative_prompt: { label: '네거티브 프롬프트', type: 'text' },
      object_key: { label: '파일', type: 'image' },
    },
    listRows: (listRequest: GetListRequest) =>
      request<GetListResponse<ImageRecord>>('post', '/image/list', listRequest),
    findClosestByExample: (exampleIds: number[]) =>
      request<Record<number, SimilarityResult>>(
        'post',
        '/image/closest-by-example',
        exampleIds,
      ),
    findSimilarByImage: (imageId: number, limit: number) =>
      request<ImagePromptSimilarityResponse>('post', '/image/similar-by-image', {
        image_id: imageId,
        limit,
      }),
    upsertRow: (items: ImageRecord[]) =>
      request<UpsertResponse[]>('post', '/image/upsert', items),
    upsertFormRow: (item: ImageRecord, files: Record<string, File | null | undefined> = {}) =>
      request<UpsertResponse>('post', '/image/upsert-form', buildUpsertFormData(item, files)),
    deleteRows: (ids: number[]) =>
      request<null>('delete', '/image/', ids).then(() => undefined),
  },

  CreatorHelpers: {
    label: '생성 도구',
    hidden: true,
    columns: {},
    listExampleRowsSortSimilar: (listRequest: GetListRequest) =>
      request<GetListResponse<ExampleSortSimilarRecord>>(
        'post',
        '/creator-helpers/example-list-sort-similar',
        listRequest,
      ),
    findSimilarExamplesByEmbedding: (embedding: number[], topN = 10) =>
      request<SimilarityResult[]>('post', '/creator-helpers/similar-examples-by-embedding', {
        embedding,
        top_n: topN,
      }),
    findSimilarExamplesByContextEmbedding: (embedding: number[], topN = 10) =>
      request<SimilarityResult[]>('post', '/creator-helpers/similar-examples-by-context-embedding', {
        embedding,
        top_n: topN,
      }),
    findSimilarImagesByPromptEmbedding: (embedding: number[], topN = 10) =>
      request<SimilarityResult[]>('post', '/creator-helpers/similar-images-by-prompt-embedding', {
        embedding,
        top_n: topN,
      }),
    syncExampleJpWords: (syncRequest?: SyncExampleJpWordsRequest) =>
      request<SyncExampleJpWordsResponse>(
        'post',
        '/creator-helpers/sync-example-jp-words',
        syncRequest,
      ),
    popTemporaryAutoFlowSeed: () =>
      request<TemporaryAutoFlowSeedResponse>(
        'post',
        '/creator-helpers/temporary-auto-flow-seed',
      ),
  },

  Audio: {
    label: '오디오',
    columns: {
      id: { label: 'ID', type: 'id' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      updated_at: { label: '수정일', type: 'datetime', readOnly: true },
      example_id: { label: '예문', type: 'fk', targetTable: 'Example', required: true },
      speaker: { label: '화자', type: 'text', required: true },
      object_key: { label: '파일', type: 'file' },
    },
    listRows: (listRequest: GetListRequest) =>
      request<GetListResponse<AudioRecord>>('post', '/audio/list', listRequest),
    upsertRow: (items: AudioRecord[]) =>
      request<UpsertResponse[]>('post', '/audio/upsert', items),
    upsertFormRow: (item: AudioRecord, files: Record<string, File | null | undefined> = {}) =>
      request<UpsertResponse>('post', '/audio/upsert-form', buildUpsertFormData(item, files)),
    deleteRows: (ids: number[]) =>
      request<null>('delete', '/audio/', ids).then(() => undefined),
  },

  UserJpWordSkill: {
    label: '단어 숙련도',
    columns: {
      id: { label: 'ID', type: 'id' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      updated_at: { label: '수정일', type: 'datetime', readOnly: true },
      user_id: { label: '사용자', type: 'text', readOnly: true },
      word_id: { label: '단어', type: 'fk', targetTable: 'JpWord', required: true },
      reading: { label: '읽기', type: 'number', required: true },
      listening: { label: '듣기', type: 'number', required: true },
      speaking: { label: '말하기', type: 'number', required: true },
    },
    listRows: (listRequest: GetListRequest) =>
      request<GetListResponse<UserJpWordSkillRecord>>('post', '/user_jp_word_skill/list', listRequest),
    upsertRow: (items: UserJpWordSkillRecord[]) =>
      request<UpsertResponse[]>('post', '/user_jp_word_skill/upsert', items),
    deleteRows: (ids: number[]) =>
      request<null>('delete', '/user_jp_word_skill/', ids).then(() => undefined),
  },

  UserText: {
    label: '사용자 텍스트',
    columns: {
      id: { label: 'ID', type: 'id' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      updated_at: { label: '수정일', type: 'datetime', readOnly: true },
      user_id: { label: '사용자', type: 'text', readOnly: true },
      title: { label: '제목', type: 'text', required: true },
      text: { label: '본문', type: 'text', required: true },
      tags: { label: '태그', type: 'text', required: true },
      youtube_url: { label: 'YouTube URL', type: 'text' },
    },
    listRows: (listRequest: GetListRequest) =>
      request<GetListResponse<UserTextRecord>>('post', '/user_text/list', listRequest),
    upsertRow: (items: UserTextRecord[]) =>
      request<UpsertResponse[]>('post', '/user_text/upsert', items),
    deleteRows: (ids: number[]) =>
      request<null>('delete', '/user_text/', ids).then(() => undefined),
  },

  ErrorReport: {
    label: '오류 제보',
    columns: {
      id: { label: 'ID', type: 'id' },
      created_at: { label: '생성일', type: 'datetime', readOnly: true },
      updated_at: { label: '수정일', type: 'datetime', readOnly: true },
      user_id: { label: '사용자', type: 'text', readOnly: true },
      example_id: { label: '예문', type: 'fk', targetTable: 'Example', required: true },
      error_type: { label: '유형', type: 'text', required: true },
      error_description: { label: '내용', type: 'text', required: true },
      is_resolved: { label: '해결됨', type: 'boolean', required: true },
    },
    listRows: (listRequest: GetListRequest) =>
      request<GetListResponse<ErrorReportRecord>>('post', '/error_report/list', listRequest),
    upsertRow: (items: ErrorReportRecord[]) =>
      request<UpsertResponse[]>('post', '/error_report/upsert', items),
    deleteRows: (ids: number[]) =>
      request<null>('delete', '/error_report/', ids).then(() => undefined),
  },
};

export type DbTableName = keyof typeof dbTables;
