import { aiFastApi } from '../../api/apiAi';
import type { LlmRequest } from '../../api/apiAi';

const TRANSLATION_SYSTEM_PROMPT = [
  'You are a Japanese to Korean translator for language-learning examples.',
  'Translate the given Japanese sentence into natural Korean.',
  'Return only the Korean translation. Do not include explanations, markdown, bullets, or quotation marks.',
].join('\n');

const WORD_MEANING_SYSTEM_PROMPT = [
  'You are a Japanese to Korean dictionary editor for language-learning examples.',
  'Infer the target word meaning from the Japanese sentence context.',
  'Return only one concise Korean meaning for the lemma. Do not include explanations, markdown, bullets, quotation marks, or multiple candidates.',
].join('\n');

const SDXL_TRANSLATION_SYSTEM_PROMPT = [
  'You are a precise English translator for image prompt preparation.',
  'Translate the given Japanese sentences into natural English.',
  'Return only valid JSON with this shape: {"previous_sentence":"...","current_sentence":"..."}.',
  'Do not include markdown, explanations, or extra keys.',
].join('\n');

const SDXL_PROMPT_SYSTEM_PROMPT = [
  'You are a stable diffusion illustrator image prompt writer.',
  'Write prompts that visually represent the current Japanese language-learning example sentence.',
  'Use any previous sentence only as context.',
  'Return only valid JSON with this shape: {"positive_prompt":"...","negative_prompt":"..."}.',
  'Each prompt must be only a comma-separated combination of English words or short noun/adjective tags.',
  'Avoid ambiguous words in the prompt; use intuitive words that leave no room for double interpretation.',
  'Each prompt must be 15 comma-separated items or fewer.',
  'Do not include style tags or quality tags in both of positive prompt and negative prompt',
  'Do not include markdown, explanations, or extra keys.',
].join('\n');

async function requestLlmAnswer(
  request: LlmRequest,
  failureMessage: string,
  emptyMessage: string,
): Promise<string> {
  const data = await aiFastApi.llm(request).catch((error: unknown) => {
    const message = error instanceof Error ? error.message : '';
    throw new Error(message ? `${failureMessage}: ${message}` : failureMessage);
  });

  if (typeof data.answer !== 'string' || !data.answer.trim()) {
    throw new Error(emptyMessage);
  }

  return data.answer.trim();
}

function parseJsonObject(answer: string, failureMessage: string): Record<string, unknown> {
  try {
    return JSON.parse(answer) as Record<string, unknown>;
  } catch {
    throw new Error(failureMessage);
  }
}

function getJsonString(
  data: Record<string, unknown>,
  key: string,
  failureMessage: string,
): string {
  const value = data[key];

  if (typeof value !== 'string' || !value.trim()) {
    throw new Error(failureMessage);
  }

  return value.trim();
}

export async function translateJapaneseSentenceToKorean(
  japaneseSentence: string,
): Promise<string> {
  return requestLlmAnswer(
    {
      system_prompt: TRANSLATION_SYSTEM_PROMPT,
      prompt: [
        `Japanese sentence: ${japaneseSentence.trim()}`,
        '',
        'Translate it into Korean.',
      ].join('\n'),
      max_tokens: 120,
      temperature: 0.2,
    },
    '한국어 번역에 실패했습니다.',
    'LLM이 빈 번역을 반환했습니다.',
  );
}

export async function fetchJapaneseWordKoreanMeaning({
  sentence,
  surface,
  lemma,
}: {
  sentence: string;
  surface: string;
  lemma: string;
}): Promise<string> {
  return requestLlmAnswer(
    {
      system_prompt: WORD_MEANING_SYSTEM_PROMPT,
      prompt: [
        `Japanese sentence: ${sentence.trim()}`,
        `Target surface: ${surface.trim()}`,
        `Target lemma: ${lemma.trim()}`,
        '',
        'Return the Korean meaning of the target lemma in this context.',
      ].join('\n'),
      max_tokens: 40,
      temperature: 0.1,
    },
    '한국어 뜻 생성에 실패했습니다.',
    'LLM이 빈 뜻을 반환했습니다.',
  );
}

export async function generateSdxlPromptsForExample({
  previousJapaneseSentence,
  japaneseSentence,
  koreanMeaning,
}: {
  previousJapaneseSentence?: string;
  japaneseSentence: string;
  koreanMeaning: string;
}): Promise<{ positivePrompt: string; negativePrompt: string }> {
  const previousSentence = previousJapaneseSentence?.trim() ?? '';
  const currentJapaneseSentence = japaneseSentence.trim();
  let answer: string;

  if (previousSentence) {
    const translationAnswer = await requestLlmAnswer(
      {
        system_prompt: SDXL_TRANSLATION_SYSTEM_PROMPT,
        prompt: [
          `Previous Japanese sentence: ${previousSentence}`,
          `Current Japanese sentence: ${currentJapaneseSentence}`,
          '',
          'Translate both sentences into English.',
        ].join('\n'),
        max_tokens: 180,
        temperature: 0.1,
      },
      '영어 번역 생성에 실패했습니다.',
      'LLM이 빈 번역을 반환했습니다.',
    );
    const translated = parseJsonObject(translationAnswer, '영어 번역 응답을 해석하지 못했습니다.');
    const translatedPreviousSentence = getJsonString(
      translated,
      'previous_sentence',
      '이전 문장 번역이 비어 있습니다.',
    );
    const translatedCurrentSentence = getJsonString(
      translated,
      'current_sentence',
      '현재 문장 번역이 비어 있습니다.',
    );

    answer = await requestLlmAnswer(
      {
        system_prompt: SDXL_PROMPT_SYSTEM_PROMPT,
        prompt: [
          `Previous sentence: ${translatedPreviousSentence}`,
          `Current sentence: ${translatedCurrentSentence}`,
          '',
          'Create SDXL prompts for an image representing the current sentence.',
        ].join('\n'),
        max_tokens: 120,
        temperature: 0.2,
      },
      'SDXL 프롬프트 생성에 실패했습니다.',
      'LLM이 빈 프롬프트를 반환했습니다.',
    );
  } else {
    answer = await requestLlmAnswer(
      {
        system_prompt: SDXL_PROMPT_SYSTEM_PROMPT,
        prompt: [
          `Japanese sentence: ${currentJapaneseSentence}`,
          `Korean meaning: ${koreanMeaning.trim()}`,
          '',
          'Create SDXL prompts for an image representing this example.',
        ].join('\n'),
        max_tokens: 140,
        temperature: 0.2,
      },
      'SDXL 프롬프트 생성에 실패했습니다.',
      'LLM이 빈 프롬프트를 반환했습니다.',
    );
  }

  const prompts = parseJsonObject(answer, 'SDXL 프롬프트 응답을 해석하지 못했습니다.');

  return {
    positivePrompt: getJsonString(
      prompts,
      'positive_prompt',
      'positive prompt가 비어 있습니다.',
    ),
    negativePrompt: getJsonString(
      prompts,
      'negative_prompt',
      'negative prompt가 비어 있습니다.',
    ),
  };
}
