'use client';

import { Send } from 'lucide-react';
import { useState } from 'react';

type RequestFormProps = {
  disabled: boolean;
  onError: (message: string) => void;
  onSubmit: (requestJson: Record<string, unknown>) => void;
};

export function EmbeddingRequestForm({ disabled, onError, onSubmit }: RequestFormProps) {
  const [text, setText] = useState('');

  function submit() {
    try {
      const trimmedText = text.trim();
      if (!trimmedText) {
        throw new Error('text 값을 입력해야 합니다.');
      }
      onSubmit({ text: trimmedText });
    } catch (error) {
      onError(error instanceof Error ? error.message : '입력값을 확인해 주세요.');
    }
  }

  return (
    <div className="grid gap-5">
      <label className="grid gap-2 text-sm font-bold">
        text
        <textarea
          className="min-h-64 rounded-lg border border-[var(--app-border)] bg-white px-3 py-2 text-sm font-semibold leading-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
      </label>
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
