import { Brain, Send } from 'lucide-react';
import { useState } from 'react';

import { formatJson, parseOptionalFloat, parseOptionalInt } from '../format';
import type { AiSession } from '../useAiSession';
import { GenerationOptionsFields } from './GenerationOptionsFields';
import type { ResponseFormat, ThinkingEffort } from './GenerationOptionsFields';

const LLM_TIMEOUT_MS = 600_000;

type LlmResponse = {
  answer: string;
};

export function LlmPanel({ session, active }: { session: AiSession; active: boolean }) {
  const [systemPrompt, setSystemPrompt] = useState('You are a concise assistant.');
  const [prompt, setPrompt] = useState('Say hello from the AI slave.');
  const [maxTokens, setMaxTokens] = useState('512');
  const [temperature, setTemperature] = useState('0.5');
  const [think, setThink] = useState(true);
  const [thinkingEffort, setThinkingEffort] = useState<ThinkingEffort>('low');
  const [responseFormat, setResponseFormat] = useState<ResponseFormat>('text');
  const [result, setResult] = useState<LlmResponse | null>(null);
  const [rawJson, setRawJson] = useState('');

  if (!active) {
    return null;
  }

  async function callLlm() {
    let payload;
    try {
      payload = {
        system_prompt: systemPrompt,
        prompt,
        max_tokens: parseOptionalInt(maxTokens, 'max tokens'),
        temperature: parseOptionalFloat(temperature, 'temperature'),
        think,
        thinking_effort: thinkingEffort,
        response_format: responseFormat,
      };
    } catch (error) {
      session.reportError(error, 'ai.llm');
      return;
    }

    try {
      const response = await session.runJob<typeof payload, LlmResponse>('ai.llm', payload, LLM_TIMEOUT_MS);
      setResult(response.payload);
      setRawJson(formatJson(response.payload));
    } catch {
      // The shared session hook records connection and job failures.
    }
  }

  return (
    <section className="tabGrid workGrid">
      <div className="panel formPanel">
        <div className="panelHeader">
          <h2>ai.llm</h2>
          <Brain size={17} aria-hidden="true" />
        </div>
        <label>
          <span>System Prompt</span>
          <textarea value={systemPrompt} onChange={(event) => setSystemPrompt(event.target.value)} rows={5} />
        </label>
        <label>
          <span>Prompt</span>
          <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={7} />
        </label>
        <div className="formGrid compact">
          <label>
            <span>Max Tokens</span>
            <input value={maxTokens} inputMode="numeric" onChange={(event) => setMaxTokens(event.target.value)} />
          </label>
          <label>
            <span>Temperature</span>
            <input value={temperature} inputMode="decimal" onChange={(event) => setTemperature(event.target.value)} />
          </label>
        </div>
        <GenerationOptionsFields
          think={think}
          thinkingEffort={thinkingEffort}
          responseFormat={responseFormat}
          onThinkChange={setThink}
          onThinkingEffortChange={setThinkingEffort}
          onResponseFormatChange={setResponseFormat}
        />
        <button
          type="button"
          className="primaryButton"
          onClick={() => {
            void callLlm();
          }}
          disabled={session.busy}
        >
          <Send size={17} aria-hidden="true" />
          <span>Send</span>
        </button>
      </div>

      <div className="panel resultPanel">
        <div className="panelHeader">
          <h2>Output</h2>
          <span>{result ? 'ready' : 'empty'}</span>
        </div>
        <pre className="answerBox">{result?.answer || 'No answer yet.'}</pre>
        <pre className="resultBox">{rawJson || 'No raw result yet.'}</pre>
      </div>
    </section>
  );
}
