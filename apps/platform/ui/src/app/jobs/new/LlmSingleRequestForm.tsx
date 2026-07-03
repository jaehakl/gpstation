'use client';

import { Send } from 'lucide-react';
import { useState } from 'react';

type RequestFormProps = {
  disabled: boolean;
  onError: (message: string) => void;
  onSubmit: (requestJson: Record<string, unknown>) => void;
};

function optionalInteger(value: string, label: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }

  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed)) {
    throw new Error(`${label} 값은 정수여야 합니다.`);
  }
  return parsed;
}

function optionalNumber(value: string, label: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }

  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) {
    throw new Error(`${label} 값은 숫자여야 합니다.`);
  }
  return parsed;
}

export function LlmSingleRequestForm({ disabled, onError, onSubmit }: RequestFormProps) {
  const [systemPrompt, setSystemPrompt] = useState('');
  const [prompt, setPrompt] = useState('');
  const [maxTokens, setMaxTokens] = useState('');
  const [temperature, setTemperature] = useState('');

  function submit() {
    try {
      const trimmedSystemPrompt = systemPrompt.trim();
      const trimmedPrompt = prompt.trim();
      if (!trimmedSystemPrompt) {
        throw new Error('system_prompt 값을 입력해야 합니다.');
      }
      if (!trimmedPrompt) {
        throw new Error('prompt 값을 입력해야 합니다.');
      }

      const requestJson: Record<string, unknown> = {
        system_prompt: trimmedSystemPrompt,
        prompt: trimmedPrompt,
      };
      const parsedMaxTokens = optionalInteger(maxTokens, 'max_tokens');
      const parsedTemperature = optionalNumber(temperature, 'temperature');
      if (parsedMaxTokens !== undefined) {
        requestJson.max_tokens = parsedMaxTokens;
      }
      if (parsedTemperature !== undefined) {
        requestJson.temperature = parsedTemperature;
      }
      onSubmit(requestJson);
    } catch (error) {
      onError(error instanceof Error ? error.message : '입력값을 확인해 주세요.');
    }
  }

  return (
    <div className="grid gap-5">
      <label className="grid gap-2 text-sm font-bold">
        system_prompt
        <textarea
          className="min-h-32 rounded-lg border border-[var(--app-border)] bg-white px-3 py-2 text-sm font-semibold leading-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
          value={systemPrompt}
          onChange={(event) => setSystemPrompt(event.target.value)}
        />
      </label>
      <label className="grid gap-2 text-sm font-bold">
        prompt
        <textarea
          className="min-h-44 rounded-lg border border-[var(--app-border)] bg-white px-3 py-2 text-sm font-semibold leading-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
        />
      </label>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="grid gap-2 text-sm font-bold">
          max_tokens
          <input
            type="number"
            step={1}
            className="h-11 rounded-lg border border-[var(--app-border)] bg-white px-3 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            value={maxTokens}
            onChange={(event) => setMaxTokens(event.target.value)}
          />
        </label>
        <label className="grid gap-2 text-sm font-bold">
          temperature
          <input
            type="number"
            step={0.1}
            className="h-11 rounded-lg border border-[var(--app-border)] bg-white px-3 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            value={temperature}
            onChange={(event) => setTemperature(event.target.value)}
          />
        </label>
      </div>
      <button
        type="button"
        className="inline-flex h-11 w-fit items-center justify-center gap-2 rounded-lg border border-[#2e2d2d] bg-[#2c2c2c] px-4 text-sm font-extrabold text-white transition hover:bg-[#1f1f1f] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:opacity-50"
        disabled={disabled}
        onClick={submit}
      >
        <Send className="h-4 w-4" aria-hidden="true" />
        {disabled ? '요청 중' : '요청 생성'}
      </button>
    </div>
  );
}
