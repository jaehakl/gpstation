'use client';

import { Send } from 'lucide-react';
import { useState } from 'react';

type RequestFormProps = {
  disabled: boolean;
  onError: (message: string) => void;
  onSubmit: (requestJson: Record<string, unknown>) => void;
};

function nonEmptyLines(value: string) {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function parseOptionalLines(value: string) {
  const lines = nonEmptyLines(value);
  return lines.length > 0 ? lines : undefined;
}

function parseSeeds(value: string) {
  if (!value.trim()) {
    return undefined;
  }

  return value.split(/\r?\n/).map((line, index) => {
    const trimmed = line.trim();
    if (!trimmed) {
      return null;
    }

    const parsed = Number(trimmed);
    if (!Number.isInteger(parsed)) {
      throw new Error(`seeds ${index + 1}번째 줄은 정수 또는 빈 줄이어야 합니다.`);
    }
    return parsed;
  });
}

function requiredNumber(value: string, label: string, min: number, max: number) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(`${label} 값은 숫자여야 합니다.`);
  }
  if (parsed < min || parsed > max) {
    throw new Error(`${label} 값은 ${min} 이상 ${max} 이하여야 합니다.`);
  }
  return parsed;
}

function requiredInteger(value: string, label: string, min: number, max: number) {
  const parsed = requiredNumber(value, label, min, max);
  if (!Number.isInteger(parsed)) {
    throw new Error(`${label} 값은 정수여야 합니다.`);
  }
  return parsed;
}

function optionalInteger(value: string, label: string, min: number, max: number) {
  if (!value.trim()) {
    return undefined;
  }
  return requiredInteger(value, label, min, max);
}

export function SdxlT2IRequestForm({ disabled, onError, onSubmit }: RequestFormProps) {
  const [prompts, setPrompts] = useState('');
  const [negativePrompts, setNegativePrompts] = useState('');
  const [seeds, setSeeds] = useState('');
  const [step, setStep] = useState('30');
  const [cfg, setCfg] = useState('7.0');
  const [height, setHeight] = useState('1024');
  const [width, setWidth] = useState('1024');
  const [strength, setStrength] = useState('1.0');
  const [maxChunkSize, setMaxChunkSize] = useState('1');
  const [seedMin, setSeedMin] = useState('0');
  const [seedMax, setSeedMax] = useState('2147483647');
  const [sampler, setSampler] = useState('euler');
  const [scheduler, setScheduler] = useState('');
  const [clipSkip, setClipSkip] = useState('');
  const [format, setFormat] = useState('png');

  function submit() {
    try {
      const parsedPrompts = nonEmptyLines(prompts);
      const trimmedSampler = sampler.trim();
      const trimmedFormat = format.trim();
      if (parsedPrompts.length === 0) {
        throw new Error('prompts 값을 한 줄 이상 입력해야 합니다.');
      }
      if (!trimmedSampler) {
        throw new Error('sampler 값을 입력해야 합니다.');
      }
      if (!trimmedFormat) {
        throw new Error('format 값을 입력해야 합니다.');
      }

      const requestJson: Record<string, unknown> = {
        prompts: parsedPrompts,
        step: requiredInteger(step, 'step', 1, 150),
        cfg: requiredNumber(cfg, 'cfg', 0, 30),
        height: requiredInteger(height, 'height', 64, 2048),
        width: requiredInteger(width, 'width', 64, 2048),
        strength: requiredNumber(strength, 'strength', 0, 1),
        max_chunk_size: requiredInteger(maxChunkSize, 'max_chunk_size', 1, 8),
        seed_min: requiredInteger(seedMin, 'seed_min', 0, Number.MAX_SAFE_INTEGER),
        seed_max: requiredInteger(seedMax, 'seed_max', 0, Number.MAX_SAFE_INTEGER),
        sampler: trimmedSampler,
        scheduler: scheduler.trim(),
        format: trimmedFormat,
      };

      const parsedNegativePrompts = parseOptionalLines(negativePrompts);
      const parsedSeeds = parseSeeds(seeds);
      const parsedClipSkip = optionalInteger(clipSkip, 'clip_skip', 1, 12);
      if (parsedNegativePrompts !== undefined) {
        requestJson.negative_prompts = parsedNegativePrompts;
      }
      if (parsedSeeds !== undefined) {
        requestJson.seeds = parsedSeeds;
      }
      if (parsedClipSkip !== undefined) {
        requestJson.clip_skip = parsedClipSkip;
      }
      onSubmit(requestJson);
    } catch (error) {
      onError(error instanceof Error ? error.message : '입력값을 확인해 주세요.');
    }
  }

  return (
    <div className="grid gap-5">
      <div className="grid gap-4 lg:grid-cols-2">
        <label className="grid gap-2 text-sm font-bold">
          prompts
          <textarea
            className="min-h-44 rounded-lg border border-[var(--app-border)] bg-white px-3 py-2 text-sm font-semibold leading-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            value={prompts}
            onChange={(event) => setPrompts(event.target.value)}
          />
        </label>
        <label className="grid gap-2 text-sm font-bold">
          negative_prompts
          <textarea
            className="min-h-44 rounded-lg border border-[var(--app-border)] bg-white px-3 py-2 text-sm font-semibold leading-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            value={negativePrompts}
            onChange={(event) => setNegativePrompts(event.target.value)}
          />
        </label>
      </div>
      <label className="grid gap-2 text-sm font-bold">
        seeds
        <textarea
          className="min-h-24 rounded-lg border border-[var(--app-border)] bg-white px-3 py-2 font-mono text-sm font-semibold leading-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
          value={seeds}
          onChange={(event) => setSeeds(event.target.value)}
        />
      </label>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <NumberField label="step" value={step} min={1} max={150} step={1} onChange={setStep} />
        <NumberField label="cfg" value={cfg} min={0} max={30} step={0.1} onChange={setCfg} />
        <NumberField label="height" value={height} min={64} max={2048} step={1} onChange={setHeight} />
        <NumberField label="width" value={width} min={64} max={2048} step={1} onChange={setWidth} />
        <NumberField label="strength" value={strength} min={0} max={1} step={0.05} onChange={setStrength} />
        <NumberField label="max_chunk_size" value={maxChunkSize} min={1} max={8} step={1} onChange={setMaxChunkSize} />
        <NumberField label="seed_min" value={seedMin} min={0} step={1} onChange={setSeedMin} />
        <NumberField label="seed_max" value={seedMax} min={0} step={1} onChange={setSeedMax} />
        <TextField label="sampler" value={sampler} onChange={setSampler} />
        <TextField label="scheduler" value={scheduler} onChange={setScheduler} />
        <NumberField label="clip_skip" value={clipSkip} min={1} max={12} step={1} onChange={setClipSkip} />
        <TextField label="format" value={format} onChange={setFormat} />
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

function NumberField({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: string;
  min?: number;
  max?: number;
  step: number;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-2 text-sm font-bold">
      {label}
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        className="h-11 rounded-lg border border-[var(--app-border)] bg-white px-3 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function TextField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-2 text-sm font-bold">
      {label}
      <input
        className="h-11 rounded-lg border border-[var(--app-border)] bg-white px-3 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
