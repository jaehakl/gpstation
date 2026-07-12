import { Settings, Send, Square, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import { Link } from 'react-router-dom';
import { GpStationClient } from '@gpstation/v1-master-js-sdk';
import type { JobEvent, JobSession } from '@gpstation/v1-master-js-sdk';
import 'katex/dist/katex.min.css';

import { API_URL } from '../../api/api';
import { useAuthStore } from '../../stores/authStore';

const CHAT_TIMEOUT_MS = 600_000;
const CHAT_SCROLL_BOTTOM_THRESHOLD_PX = 48;

type ChatResponse = {
  model: string;
  answer: string;
  context_window: number;
  prompt_tokens: number;
  max_response_tokens: number;
  remaining_tokens: number;
  cache_enabled: boolean;
};

type ChatPayload = {
  model: string;
  system_prompt?: string;
  prompt: string;
  max_tokens?: number;
  temperature?: number;
  context_size?: number;
  top_p?: number;
  think: boolean;
  thinking_effort: ThinkingEffort;
  response_format: ResponseFormat;
};

type ThinkingEffort = 'default' | 'low';
type ResponseFormat = 'text' | 'json';

type LlmModelSummary = {
  name: string;
  context_size: number;
  top_p: number;
};

type LlmModelListResponse = {
  default_model: string;
  models: LlmModelSummary[];
};

type ChatMessage = {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  streaming: boolean;
};

export default function ChatPage() {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const [systemPrompt, setSystemPrompt] = useState('You are a helpful conversational assistant.');
  const [prompt, setPrompt] = useState('');
  const [maxTokens, setMaxTokens] = useState('8192');
  const [temperature, setTemperature] = useState('1.0');
  const [contextSize, setContextSize] = useState('');
  const [topP, setTopP] = useState('');
  const [think, setThink] = useState(false);
  const [thinkingEffort, setThinkingEffort] = useState<ThinkingEffort>('low');
  const [responseFormat, setResponseFormat] = useState<ResponseFormat>('text');
  const [llmModels, setLlmModels] = useState<LlmModelSummary[]>([]);
  const [defaultModel, setDefaultModel] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [context, setContext] = useState<ChatResponse | null>(null);
  const [session, setSession] = useState<JobSession | null>(null);
  const [status, setStatus] = useState('closed');
  const [busy, setBusy] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messageIdRef = useRef(0);
  const activeAssistantMessageIdRef = useRef<number | null>(null);
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);
  const transcriptAtBottomRef = useRef(true);
  const forceTranscriptScrollRef = useRef(false);
  const sessionRef = useRef<JobSession | null>(null);
  const pendingDeltaRef = useRef('');
  const deltaFrameRef = useRef<number | null>(null);
  const modelListRequestRef = useRef<Promise<void> | null>(null);

  const client = useMemo(
    () =>
      new GpStationClient({
        apiBaseUrl: API_URL,
        authMode: 'cookie',
        jobApiPrefix: '/web/jobs',
      }),
    [],
  );

  const chatOpen = session !== null && !session.closed;
  const canUseChat = Boolean(user && user.role !== 'unauthorized');
  const selectedModelSettings = useMemo(
    () => llmModels.find((model) => model.name === selectedModel) ?? null,
    [llmModels, selectedModel],
  );

  const loadLlmModels = useCallback(() => {
    if (modelListRequestRef.current) {
      return modelListRequestRef.current;
    }

    setModelsLoading(true);
    setModelsError(null);
    const request = client
      .runJob<Record<string, never>, LlmModelListResponse>('ai.llm.models', {}, {
        slaveAppId: 'ai',
        timeoutMs: CHAT_TIMEOUT_MS,
      })
      .then((result) => {
        const payload = result.payload;
        const models = Array.isArray(payload.models)
          ? payload.models.filter(
              (model): model is LlmModelSummary =>
                typeof model?.name === 'string' &&
                model.name.trim().length > 0 &&
                typeof model.context_size === 'number' &&
                typeof model.top_p === 'number',
            )
          : [];
        if (models.length === 0) {
          throw new Error('사용 가능한 LLM 모델이 없습니다.');
        }
        const backendDefault =
          typeof payload.default_model === 'string' && models.some((model) => model.name === payload.default_model)
            ? payload.default_model
            : models[0].name;
        setLlmModels(models);
        setDefaultModel(backendDefault);
        setSelectedModel((current) =>
          current && models.some((model) => model.name === current) ? current : backendDefault,
        );
      })
      .catch((nextError: unknown) => {
        setLlmModels([]);
        setDefaultModel('');
        setSelectedModel('');
        setModelsError(nextError instanceof Error ? nextError.message : String(nextError));
      })
      .finally(() => {
        modelListRequestRef.current = null;
        setModelsLoading(false);
      });
    modelListRequestRef.current = request;
    return request;
  }, [client]);

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  useEffect(() => {
    if (authReady && canUseChat) {
      void loadLlmModels();
    }
  }, [authReady, canUseChat, loadLlmModels]);

  useEffect(() => {
    if (!forceTranscriptScrollRef.current && !transcriptAtBottomRef.current) {
      return;
    }
    transcriptEndRef.current?.scrollIntoView({ block: 'end' });
    forceTranscriptScrollRef.current = false;
    transcriptAtBottomRef.current = true;
  }, [messages, busy]);

  useEffect(() => {
    return () => {
      sessionRef.current?.close();
      if (deltaFrameRef.current !== null) {
        window.cancelAnimationFrame(deltaFrameRef.current);
      }
    };
  }, []);

  if (!authReady) {
    return <div className="centerState">인증 확인 중</div>;
  }

  if (!user || user.role === 'unauthorized') {
    return (
      <div className="centerState">
        <div className="loginBox panel">
          <p className="eyebrow">AI Chat</p>
          <h1>로그인이 필요합니다</h1>
          <p className="mutedText">AI Chat은 승인된 계정으로 로그인한 뒤 사용할 수 있습니다.</p>
          <Link to="/login" className="button primaryButton fullButton" style={{ marginTop: 14 }}>
            로그인
          </Link>
        </div>
      </div>
    );
  }

  function nextMessageId(): number {
    const id = messageIdRef.current + 1;
    messageIdRef.current = id;
    return id;
  }

  function queueDelta(messageId: number, delta: string) {
    if (activeAssistantMessageIdRef.current !== messageId) {
      return;
    }
    pendingDeltaRef.current += delta;
    if (deltaFrameRef.current !== null) {
      return;
    }
    deltaFrameRef.current = window.requestAnimationFrame(() => {
      const bufferedDelta = pendingDeltaRef.current;
      pendingDeltaRef.current = '';
      deltaFrameRef.current = null;
      setMessages((items) =>
        items.map((item) =>
          item.id === messageId && item.streaming ? { ...item, content: item.content + bufferedDelta } : item,
        ),
      );
    });
  }

  function finishAssistant(messageId: number, answer: string) {
    if (deltaFrameRef.current !== null) {
      window.cancelAnimationFrame(deltaFrameRef.current);
      deltaFrameRef.current = null;
    }
    pendingDeltaRef.current = '';
    setMessages((items) =>
      items.map((item) => (item.id === messageId ? { ...item, content: answer, streaming: false } : item)),
    );
    if (activeAssistantMessageIdRef.current === messageId) {
      activeAssistantMessageIdRef.current = null;
    }
  }

  function handleChatEvent(event: JobEvent, assistantMessageId: number) {
    if (activeAssistantMessageIdRef.current !== assistantMessageId || event.type !== 'ai.chat.delta') {
      return;
    }
    const delta = readChatDelta(event.payload);
    if (delta) {
      queueDelta(assistantMessageId, delta);
    }
  }

  function handleTranscriptScroll() {
    const element = transcriptRef.current;
    if (!element) {
      return;
    }
    transcriptAtBottomRef.current =
      element.scrollHeight - element.scrollTop - element.clientHeight <= CHAT_SCROLL_BOTTOM_THRESHOLD_PX;
  }

  async function callChat() {
    if (modelsLoading || !selectedModel) {
      setError(modelsLoading ? 'LLM 모델 목록을 불러오는 중입니다.' : '사용할 LLM 모델을 선택해야 합니다.');
      setSettingsOpen(true);
      return;
    }
    const trimmedPrompt = prompt.trim();
    if (!trimmedPrompt) {
      setError('prompt is required');
      return;
    }
    const existingSession = sessionRef.current && !sessionRef.current.closed ? sessionRef.current : null;
    const trimmedSystemPrompt = systemPrompt.trim();
    if (!existingSession && !trimmedSystemPrompt) {
      setError('system prompt is required for a new chat');
      setSettingsOpen(true);
      return;
    }

    let payload: ChatPayload;
    try {
      payload = {
        model: selectedModel,
        prompt: trimmedPrompt,
        max_tokens: parseOptionalInt(maxTokens, 'max tokens'),
        temperature: parseOptionalFloat(temperature, 'temperature'),
        context_size: parseOptionalInt(contextSize, 'context size'),
        top_p: parseOptionalFloat(topP, 'top p'),
        think,
        thinking_effort: thinkingEffort,
        response_format: responseFormat,
      };
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
      setSettingsOpen(true);
      return;
    }
    if (!existingSession) {
      payload.system_prompt = trimmedSystemPrompt;
    }

    const userMessage: ChatMessage = {
      id: nextMessageId(),
      role: 'user',
      content: trimmedPrompt,
      streaming: false,
    };
    const assistantMessageId = nextMessageId();
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      streaming: true,
    };

    activeAssistantMessageIdRef.current = assistantMessageId;
    forceTranscriptScrollRef.current = true;
    setBusy(true);
    setError(null);
    setStatus('waiting for result');
    setMessages((items) => [
      ...items.map((item) => (item.streaming ? { ...item, streaming: false } : item)),
      userMessage,
      assistantMessage,
    ]);
    setPrompt('');

    try {
      let response: ChatResponse;
      if (existingSession) {
        const result = await existingSession.call<ChatPayload, ChatResponse>('ai.chat', payload, {
          timeoutMs: CHAT_TIMEOUT_MS,
          onEvent: (event) => handleChatEvent(event, assistantMessageId),
        });
        response = result.payload;
      } else {
        const result = await client.runJob<ChatPayload, ChatResponse>('ai.chat', payload, {
          slaveAppId: 'ai',
          timeoutMs: CHAT_TIMEOUT_MS,
          autoFinish: false,
          onEvent: (event) => handleChatEvent(event, assistantMessageId),
          onStatus: setStatus,
        });
        response = result.payload;
        sessionRef.current = result.session;
        setSession(result.session);
        setStatus('open');
      }
      finishAssistant(assistantMessageId, response.answer);
      setContext(response);
      setStatus('response complete');
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : String(nextError);
      finishAssistant(assistantMessageId, `Error: ${message}`);
      setError(message);
      setStatus('failed');
    } finally {
      setBusy(false);
    }
  }

  async function finishChatSession() {
    const currentSession = sessionRef.current;
    if (!currentSession || currentSession.closed) {
      sessionRef.current = null;
      setSession(null);
      setMessages([]);
      setContext(null);
      setPrompt('');
      activeAssistantMessageIdRef.current = null;
      setError(null);
      setStatus('closed');
      return;
    }
    setBusy(true);
    setError(null);
    setStatus('closing');
    try {
      await currentSession.finish({ timeoutMs: CHAT_TIMEOUT_MS });
    } catch {
      currentSession.close();
    } finally {
      sessionRef.current = null;
      setSession(null);
      setMessages([]);
      setContext(null);
      setPrompt('');
      activeAssistantMessageIdRef.current = null;
      setError(null);
      setStatus('closed');
      setBusy(false);
    }
  }

  return (
    <div className="chatPage">
      <div className="chatSurface">
        <div className="chatStatusBar">
          <span>{formatChatContext(context, chatOpen ? 'session open' : status)}</span>
          {error || modelsError ? <strong>{error ?? modelsError}</strong> : null}
        </div>
        <div className="chatTranscript" ref={transcriptRef} onScroll={handleTranscriptScroll}>
          {messages.map((item) => (
            <div key={item.id} className={`chatMessage ${item.role}`}>
              <div className={item.role === 'user' ? 'chatBubble' : 'chatMarkdown'}>
                {item.role === 'assistant' ? (
                  <AssistantMessageContent content={item.content || (item.streaming ? '...' : '')} />
                ) : (
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, [remarkMath, { singleDollarTextMath: true }]]}
                    rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
                  >
                    {formatChatMarkdown(item.content || (item.streaming ? '...' : ''), item.role)}
                  </ReactMarkdown>
                )}
              </div>
            </div>
          ))}
          {messages.length === 0 ? <p className="emptyText">무엇이든 물어보세요.</p> : null}
          <div ref={transcriptEndRef} />
        </div>
        <div className="chatComposer">
          <label className="field">
            <span>Prompt</span>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) {
                  return;
                }
                event.preventDefault();
                if (!busy && !modelsLoading && selectedModel) {
                  void callChat();
                }
              }}
              rows={4}
            />
          </label>
          <div className="chatComposerActions">
            <button
              type="button"
              className="button primaryButton"
              onClick={callChat}
              disabled={busy || modelsLoading || !selectedModel}
            >
              <Send size={17} aria-hidden="true" />
              Send
            </button>
            <button type="button" className="button" onClick={finishChatSession} disabled={!chatOpen || busy}>
              <Square size={16} aria-hidden="true" />
              End Chat
            </button>
            <button type="button" className="button" onClick={() => setSettingsOpen(true)}>
              <Settings size={16} aria-hidden="true" />
              Settings
            </button>
          </div>
        </div>
      </div>

      {settingsOpen ? (
        <div className="modalBackdrop" role="presentation" onMouseDown={() => setSettingsOpen(false)}>
          <div
            className="settingsModal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="chat-settings-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modalHeader">
              <h2 id="chat-settings-title">AI Chat Settings</h2>
              <button type="button" className="button smallButton" onClick={() => setSettingsOpen(false)}>
                <X size={16} aria-hidden="true" />
                닫기
              </button>
            </div>
            <label className="field">
              <span>Model</span>
              <select
                value={selectedModel}
                onChange={(event) => setSelectedModel(event.target.value)}
                disabled={busy || modelsLoading || llmModels.length === 0}
              >
                {llmModels.length === 0 ? (
                  <option value="">{modelsLoading ? '모델 목록을 불러오는 중' : '선택 가능한 모델 없음'}</option>
                ) : null}
                {llmModels.map((model) => (
                  <option key={model.name} value={model.name}>
                    {model.name === defaultModel ? `${model.name} (default)` : model.name}
                  </option>
                ))}
              </select>
              <span className="mutedText">
                {selectedModelSettings
                  ? `기본 context size ${selectedModelSettings.context_size}, top p ${selectedModelSettings.top_p}`
                  : '사용할 LLM 모델을 선택하세요.'}
              </span>
            </label>
            {modelsError ? (
              <div className="message danger modelListError">
                <span>{modelsError}</span>
                <button
                  type="button"
                  className="button smallButton"
                  disabled={modelsLoading}
                  onClick={() => {
                    void loadLlmModels();
                  }}
                >
                  목록 다시 불러오기
                </button>
              </div>
            ) : null}
            <label className="field">
              <span>System Prompt</span>
              <textarea
                value={systemPrompt}
                onChange={(event) => setSystemPrompt(event.target.value)}
                rows={5}
                disabled={chatOpen}
              />
            </label>
            <div className="formGrid">
              <label className="field">
                <span>Max Tokens</span>
                <input value={maxTokens} inputMode="numeric" onChange={(event) => setMaxTokens(event.target.value)} />
              </label>
              <label className="field">
                <span>Temperature</span>
                <input value={temperature} inputMode="decimal" onChange={(event) => setTemperature(event.target.value)} />
              </label>
              <label className="field">
                <span>Context Size</span>
                <input
                  value={contextSize}
                  inputMode="numeric"
                  placeholder={selectedModelSettings ? String(selectedModelSettings.context_size) : ''}
                  onChange={(event) => setContextSize(event.target.value)}
                />
              </label>
              <label className="field">
                <span>Top P</span>
                <input
                  value={topP}
                  inputMode="decimal"
                  placeholder={selectedModelSettings ? String(selectedModelSettings.top_p) : ''}
                  onChange={(event) => setTopP(event.target.value)}
                />
              </label>
            </div>
            <label className="checkField">
              <input
                type="checkbox"
                checked={think}
                onChange={(event) => setThink(event.target.checked)}
              />
              <span>Enable Thinking</span>
            </label>
            <div className="formGrid">
              <label className="field">
                <span>Thinking Effort</span>
                <select
                  value={thinkingEffort}
                  disabled={!think}
                  onChange={(event) => setThinkingEffort(event.target.value as ThinkingEffort)}
                >
                  <option value="low">LOW</option>
                  <option value="default">DEFAULT</option>
                </select>
                <span className="mutedText">LOW는 짧고 효율적인 추론을 유도하지만 토큰 수를 보장하지 않습니다.</span>
              </label>
              <label className="field">
                <span>Response Format</span>
                <select
                  value={responseFormat}
                  onChange={(event) => setResponseFormat(event.target.value as ResponseFormat)}
                >
                  <option value="text">Text</option>
                  <option value="json">JSON</option>
                </select>
              </label>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function AssistantMessageContent({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, [remarkMath, { singleDollarTextMath: true }]]}
      rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
    >
      {formatChatMarkdown(content, 'assistant')}
    </ReactMarkdown>
  );
}

function readChatDelta(payload: unknown): string {
  if (!payload || typeof payload !== 'object' || !('delta' in payload)) {
    return '';
  }
  const delta = (payload as { delta?: unknown }).delta;
  return typeof delta === 'string' ? delta : '';
}

function formatChatContext(context: ChatResponse | null, fallback: string): string {
  if (!context) {
    return fallback;
  }
  const usedTokens = Math.max(0, context.context_window - context.remaining_tokens);
  const cache = context.cache_enabled ? 'cache on' : 'cache off';
  return `${context.model}, ${usedTokens} / ${context.context_window} tokens, ${context.remaining_tokens} remaining, ${cache}`;
}

function formatChatMarkdown(content: string, role: ChatMessage['role']): string {
  if (role !== 'assistant') {
    return content;
  }
  return withMarkdownCodeSegments(content, (segment) =>
    normalizeCollapsedMarkdownTables(segment).replace(
      /(?<=[^\s*_])(\*\*\*|\*\*|\*|___|__|_)(?=\p{Script=Hangul})/gu,
      '$1 ',
    ),
  );
}

function normalizeCollapsedMarkdownTables(segment: string): string {
  return segment
    .split('\n')
    .map((line) => {
      if (!looksLikeCollapsedMarkdownTable(line)) {
        return line;
      }
      const candidate = line.replace(/\|\s+\|/g, '|\n|');
      return looksLikeMarkdownTable(candidate) ? candidate : line;
    })
    .join('\n');
}

function looksLikeCollapsedMarkdownTable(line: string): boolean {
  const pipeCount = line.match(/\|/g)?.length ?? 0;
  return pipeCount >= 8 && /\|\s+\|/.test(line);
}

function looksLikeMarkdownTable(content: string): boolean {
  const rows = content
    .split('\n')
    .map((row) => row.trim())
    .filter(Boolean);
  return rows.length >= 2 && rows[0].startsWith('|') && rows[0].endsWith('|') && isMarkdownTableDivider(rows[1]);
}

function isMarkdownTableDivider(row: string): boolean {
  return /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(row);
}

function withMarkdownCodeSegments(content: string, formatText: (segment: string) => string): string {
  let index = 0;
  let formatted = '';
  while (index < content.length) {
    const fenceIndex = content.indexOf('```', index);
    const inlineIndex = content.indexOf('`', index);
    const nextCodeIndex = pickNextCodeIndex(fenceIndex, inlineIndex);
    if (nextCodeIndex === -1) {
      formatted += formatText(content.slice(index));
      break;
    }
    formatted += formatText(content.slice(index, nextCodeIndex));
    if (content.startsWith('```', nextCodeIndex)) {
      const fenceEnd = content.indexOf('```', nextCodeIndex + 3);
      const endIndex = fenceEnd === -1 ? content.length : fenceEnd + 3;
      formatted += content.slice(nextCodeIndex, endIndex);
      index = endIndex;
      continue;
    }
    const inlineEnd = content.indexOf('`', nextCodeIndex + 1);
    const endIndex = inlineEnd === -1 ? content.length : inlineEnd + 1;
    formatted += content.slice(nextCodeIndex, endIndex);
    index = endIndex;
  }
  return formatted;
}

function pickNextCodeIndex(fenceIndex: number, inlineIndex: number): number {
  if (fenceIndex === -1) {
    return inlineIndex;
  }
  if (inlineIndex === -1) {
    return fenceIndex;
  }
  return Math.min(fenceIndex, inlineIndex);
}

function parseOptionalInt(value: string, label: string): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed)) {
    throw new Error(`${label} must be an integer`);
  }
  return parsed;
}

function parseOptionalFloat(value: string, label: string): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) {
    throw new Error(`${label} must be a number`);
  }
  return parsed;
}
