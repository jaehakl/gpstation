// YOU MUST OPEN ALL FRONTEND SOURCE FILES with UTF-8 ENCODING to READ KOREAN CHARACTERS CORRECTLY.

export type UserData = {
  id: string;
  email?: string | null;
  display_name?: string | null;
  picture_url?: string | null;
  is_active?: boolean | null;
  created_at?: string | null;
  updated_at?: string | null;
  roles: string[];
};

export type GetListRequest = {
  offset: number;
  limit: number | null;
  selected_ids: number[];
  search_text: string | null;
  text_filter: Record<string, string[]>;
  filter: Record<string, unknown[]>;
  sort: [string, 'asc' | 'desc'] | null;
  random?: boolean;
};

export type GetListResponse<T> = {
  total: number;
  items: T[];
};

export type UpsertResponse = {
  id: number;
  fk_not_found?: Record<string, number[]> | null;
};

export type ExampleRecord = {
  id?: number;
  created_at?: string | null;
  updated_at?: string | null;
  jp_text: string;
  kr_text: string;
  context?: string | null;
  prompt?: string | null;
  negative_prompt?: string | null;
  context_embedding?: number[] | null;
  text_embedding?: number[] | null;
  prompt_embedding?: number[] | null;
  jp_words?: number[] | null;
  audios?: number[] | null;
  error_reports?: number[] | null;
};

export type SimilarityResult = {
  id: number;
  score: number;
};

export type ExampleSortSimilarRecord = ExampleRecord & {
  similar_prompt_image?: SimilarityResult | null;
  similar_context_text_example?: SimilarityResult | null;
  similar_text_context_example?: SimilarityResult | null;
};

export type SyncExampleJpWordsRequest = {
  start_id: number;
  end_id: number;
  limit?: number;
};

export type SyncExampleJpWordsResponse = {
  examples_checked: number;
  examples_updated: number;
  jp_words_added: number;
  lemma_ids_without_jp_word: number[];
  last_example_id?: number | null;
  next_start_id?: number | null;
};

export type TemporaryAutoFlowSeedResponse = {
  source_sentence: string;
  seed_word: string;
};

export type JpWordRecord = {
  id?: number;
  created_at?: string | null;
  updated_at?: string | null;
  lemma_id: number;
  lemma: string;
  kr_mean: string;
  examples?: number[] | null;
  user_word_skills?: number[] | null;
};

export type ImageRecord = {
  id?: number;
  created_at?: string | null;
  updated_at?: string | null;
  prompt?: string | null;
  negative_prompt?: string | null;
  prompt_embedding?: number[] | null;
  object_key?: string | null;
};

export type ImagePromptSimilarityResponse = {
  similar_image_ids: number[];
  similar_example_ids: number[];
};

export type AudioRecord = {
  id?: number;
  created_at?: string | null;
  updated_at?: string | null;
  example_id: number;
  speaker: string;
  object_key?: string | null;
};

export type UserJpWordSkillRecord = {
  id?: number;
  created_at?: string | null;
  updated_at?: string | null;
  user_id?: string | null;
  word_id: number;
  reading: number;
  listening: number;
  speaking: number;
};

export type AnalyzeJapaneseTextSkillPayload = number | {
  reading?: number | null;
  listening?: number | null;
  speaking?: number | null;
  updated_at?: string | null;
  updatedAt?: string | null;
};

export type AnalyzeJapaneseTextSkills =
  | Record<string, AnalyzeJapaneseTextSkillPayload>
  | Array<{
      word_id?: number | null;
      wordId?: number | null;
      reading?: number | null;
      listening?: number | null;
      speaking?: number | null;
      updated_at?: string | null;
      updatedAt?: string | null;
    }>;

export type AnalyzeJapaneseWordSkill = {
  id?: number | null;
  user_id?: string | null;
  word_id: number;
  reading: number;
  listening: number;
  speaking: number;
  created_at?: string | null;
  updated_at?: string | null;
};

export type AnalyzeJapaneseWord = {
  id: string;
  word_id: number | null;
  lemma_id: number | null;
  surface: string;
  lemma: string;
  jpPron: string;
  krMean: string;
  userWordSkill: AnalyzeJapaneseWordSkill | null;
};

export type AnalyzeJapaneseTextResponse = {
  words: AnalyzeJapaneseWord[];
};

export type ExampleContextPlayResponse = {
  example: ExampleRecord;
  image_url: string | null;
  audio_urls: string[];
  analysis: AnalyzeJapaneseTextResponse;
  similar_examples: ExampleRecord[];
};

export type UserTextRecord = {
  id?: number;
  created_at?: string | null;
  updated_at?: string | null;
  user_id?: string | null;
  title: string;
  text: string;
  tags: string;
  youtube_url?: string | null;
};

export type ErrorReportRecord = {
  id?: number;
  created_at?: string | null;
  updated_at?: string | null;
  user_id?: string | null;
  example_id: number;
  error_type: string;
  error_description: string;
  is_resolved: boolean;
};
