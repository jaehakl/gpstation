import { Settings, Send, Square, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Link } from 'react-router-dom';
import { GpStationClient } from '@gpstation/v1-master-js-sdk';
import type { JobEvent, JobSession } from '@gpstation/v1-master-js-sdk';

import { API_URL } from '../../api/api';
import { useAuthStore } from '../../stores/authStore';

const CHAT_TIMEOUT_MS = 600_000;

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
  const [maxTokens, setMaxTokens] = useState('512');
  const [temperature, setTemperature] = useState('0.5');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [context, setContext] = useState<ChatResponse | null>(null);
  const [session, setSession] = useState<JobSession | null>(null);
  const [status, setStatus] = useState('closed');
  const [busy, setBusy] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messageIdRef = useRef(0);
  const activeAssistantMessageIdRef = useRef<number | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);
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
    transcriptEndRef.current?.scrollIntoView({ block: 'end' });
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
      setStatus('closed');
      return;
    }
    setBusy(true);
    setError(null);
    setStatus('closing');
    try {
      await currentSession.finish({ timeoutMs: CHAT_TIMEOUT_MS });
      setStatus('closed');
    } catch (nextError) {
      currentSession.close();
      setError(nextError instanceof Error ? nextError.message : String(nextError));
      setStatus('failed');
    } finally {
      sessionRef.current = null;
      setSession(null);
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
        <div className="chatTranscript">
          {messages.map((item) => (
            <div key={item.id} className={`chatMessage ${item.role}`}>
              <div className={item.role === 'user' ? 'chatBubble' : 'chatMarkdown'}>
                <ReactMarkdown>{formatChatMarkdown(item.content || (item.streaming ? '...' : ''), item.role)}</ReactMarkdown>
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
          </div>
        </div>
      ) : null}
    </div>
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
  return `${usedTokens} / ${context.context_window} tokens, ${context.remaining_tokens} remaining, ${cache}`;
}

function formatChatMarkdown(content: string, role: ChatMessage['role']): string {
  if (role !== 'assistant') {
    return content;
  }
  return withMarkdownCodeSegments(content, (segment) =>
    segment.replace(/(?<=[^\s*_])(\*\*\*|\*\*|\*|___|__|_)(?=[가-힣])/g, '$1 '),
  );
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
