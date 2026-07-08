import { Settings, Send, Square, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
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
  answer: string;
  context_window: number;
  prompt_tokens: number;
  max_response_tokens: number;
  remaining_tokens: number;
  cache_enabled: boolean;
};

type ChatPayload = {
  system_prompt?: string;
  prompt: string;
  max_tokens?: number;
  temperature?: number;
  enable_thinking?: boolean;
};

type ChatMessage = {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  streaming: boolean;
};

type AssistantThinkParts = {
  visible: string;
  thinking: string;
  thinkingInProgress: boolean;
};

const THINKING_TEXT_HEADER_PATTERN =
  /^\s*(?:here(?:'|’)?s\s+a\s+thinking\s+process|thinking\s+process|thought\s+process)\s*:\s*/i;
const THINKING_ANSWER_HEADER_PATTERN = /(?:^|\n)\s*(?:final\s+answer|answer|response)\s*:\s*/i;

export default function ChatPage() {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const [systemPrompt, setSystemPrompt] = useState('You are a helpful conversational assistant.');
  const [prompt, setPrompt] = useState('');
  const [maxTokens, setMaxTokens] = useState('8192');
  const [temperature, setTemperature] = useState('1.0');
  const [enableThinking, setEnableThinking] = useState(false);
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

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

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

  function appendDelta(messageId: number, delta: string) {
    if (activeAssistantMessageIdRef.current !== messageId) {
      return;
    }
    setMessages((items) =>
      items.map((item) =>
        item.id === messageId && item.streaming ? { ...item, content: item.content + delta } : item,
      ),
    );
  }

  function finishAssistant(messageId: number, answer: string) {
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
      appendDelta(assistantMessageId, delta);
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
        prompt: trimmedPrompt,
        max_tokens: parseOptionalInt(maxTokens, 'max tokens'),
        temperature: parseOptionalFloat(temperature, 'temperature'),
        enable_thinking: enableThinking,
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
          {error ? <strong>{error}</strong> : null}
        </div>
        <div className="chatTranscript" ref={transcriptRef} onScroll={handleTranscriptScroll}>
          {messages.map((item) => (
            <div key={item.id} className={`chatMessage ${item.role}`}>
              <div className={item.role === 'user' ? 'chatBubble' : 'chatMarkdown'}>
                {item.role === 'assistant' ? (
                  <AssistantMessageContent content={item.content || (item.streaming ? '...' : '')} streaming={item.streaming} />
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
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={4} />
          </label>
          <div className="chatComposerActions">
            <button type="button" className="button primaryButton" onClick={callChat} disabled={busy}>
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
            </div>
            <label className="checkField">
              <input
                type="checkbox"
                checked={enableThinking}
                onChange={(event) => setEnableThinking(event.target.checked)}
              />
              <span>Allow Thinking</span>
            </label>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function AssistantMessageContent({ content, streaming }: { content: string; streaming: boolean }) {
  const parts = parseAssistantThinkParts(content, streaming);

  if (!parts) {
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm, [remarkMath, { singleDollarTextMath: true }]]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
      >
        {formatChatMarkdown(content, 'assistant')}
      </ReactMarkdown>
    );
  }

  return (
    <>
      {parts.thinking || parts.thinkingInProgress ? (
        <details className="thinkBlock">
          <summary className="thinkSummary">{parts.thinkingInProgress ? '생각 과정 생성 중' : '생각 과정'}</summary>
          <div className="thinkContent">{parts.thinking.trim() || '아직 생각 과정이 생성되는 중입니다.'}</div>
        </details>
      ) : null}
      {parts.visible ? (
        <ReactMarkdown
          remarkPlugins={[remarkGfm, [remarkMath, { singleDollarTextMath: true }]]}
          rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
        >
          {formatChatMarkdown(parts.visible, 'assistant')}
        </ReactMarkdown>
      ) : null}
    </>
  );
}

function parseAssistantThinkParts(content: string, streaming: boolean): AssistantThinkParts | null {
  const thinkTagPattern = /<\/?think\s*>|<\|channel>|<channel\|>/gi;
  const parts: AssistantThinkParts = {
    visible: '',
    thinking: '',
    thinkingInProgress: false,
  };
  let inThinking = false;
  let index = 0;
  let match = thinkTagPattern.exec(content);

  while (match !== null) {
    const segment = content.slice(index, match.index);
    if (inThinking) {
      parts.thinking += segment;
    } else {
      parts.visible += segment;
    }
    inThinking = isThinkingStartMarker(match[0]);
    index = match.index + match[0].length;
    match = thinkTagPattern.exec(content);
  }

  if (index === 0) {
    return parseTextThinkParts(content, streaming);
  }

  if (inThinking) {
    parts.thinking += content.slice(index);
  } else {
    parts.visible += content.slice(index);
  }
  parts.thinkingInProgress = inThinking;

  return parts;
}

function isThinkingStartMarker(marker: string): boolean {
  const normalized = marker.toLowerCase();
  return normalized === '<|channel>' || normalized.startsWith('<think');
}

function parseTextThinkParts(content: string, streaming: boolean): AssistantThinkParts | null {
  const headerMatch = THINKING_TEXT_HEADER_PATTERN.exec(content);
  if (!headerMatch) {
    return null;
  }

  const remainder = content.slice(headerMatch[0].length);
  const answerMatch = THINKING_ANSWER_HEADER_PATTERN.exec(remainder);
  if (!answerMatch) {
    return {
      visible: '',
      thinking: remainder,
      thinkingInProgress: streaming,
    };
  }

  return {
    visible: remainder.slice(answerMatch.index + answerMatch[0].length),
    thinking: remainder.slice(0, answerMatch.index),
    thinkingInProgress: false,
  };
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
  return `${usedTokens} / ${context.context_window} tokens, ${context.remaining_tokens} remaining, ${cache}`;
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
