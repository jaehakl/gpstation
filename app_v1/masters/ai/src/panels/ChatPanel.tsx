import { MessageCircle, Send, Square } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import type { JobEvent, JobSession } from '@gpstation/v1-master-js-sdk';

import { parseOptionalFloat, parseOptionalInt } from '../format';
import type { AiSession } from '../useAiSession';
import { GenerationOptionsFields } from './GenerationOptionsFields';
import type { ResponseFormat, ThinkingEffort } from './GenerationOptionsFields';

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
  think: boolean;
  thinking_effort: ThinkingEffort;
  response_format: ResponseFormat;
};

type ChatMessage = {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  streaming: boolean;
};

export function ChatPanel({ session, active }: { session: AiSession; active: boolean }) {
  const [systemPrompt, setSystemPrompt] = useState('You are a helpful conversational assistant.');
  const [prompt, setPrompt] = useState('Say hello from the streaming chat handler.');
  const [maxTokens, setMaxTokens] = useState('512');
  const [temperature, setTemperature] = useState('0.5');
  const [think, setThink] = useState(true);
  const [thinkingEffort, setThinkingEffort] = useState<ThinkingEffort>('low');
  const [responseFormat, setResponseFormat] = useState<ResponseFormat>('text');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [context, setContext] = useState<ChatResponse | null>(null);
  const [jobSession, setJobSession] = useState<JobSession | null>(null);
  const [chatBusy, setChatBusy] = useState(false);
  const messageIdRef = useRef(0);
  const activeAssistantMessageIdRef = useRef<number | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);
  const jobSessionRef = useRef<JobSession | null>(null);
  const pendingDeltaRef = useRef('');
  const deltaFrameRef = useRef<number | null>(null);

  const chatOpen = jobSession !== null && !jobSession.closed;

  useEffect(() => {
    jobSessionRef.current = jobSession;
  }, [jobSession]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ block: 'end' });
  }, [messages, chatBusy]);

  useEffect(() => {
    return () => {
      jobSessionRef.current?.close();
      if (deltaFrameRef.current !== null) {
        window.cancelAnimationFrame(deltaFrameRef.current);
      }
    };
  }, [session.client]);

  if (!active) {
    return null;
  }

  function nextMessageId() {
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

  async function callChat() {
    const trimmedPrompt = prompt.trim();
    const existingSession = jobSessionRef.current && !jobSessionRef.current.closed ? jobSessionRef.current : null;
    const trimmedSystemPrompt = systemPrompt.trim();
    if (!trimmedPrompt || (!existingSession && !trimmedSystemPrompt)) {
      session.reportError(
        new Error(!trimmedPrompt ? 'prompt is required' : 'system prompt is required for a new chat'),
        'ai.chat',
      );
      return;
    }

    let payload: ChatPayload;
    try {
      payload = {
        prompt: trimmedPrompt,
        max_tokens: parseOptionalInt(maxTokens, 'max tokens'),
        temperature: parseOptionalFloat(temperature, 'temperature'),
        think,
        thinking_effort: thinkingEffort,
        response_format: responseFormat,
      };
    } catch (error) {
      session.reportError(error, 'ai.chat');
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
    setChatBusy(true);
    setMessages((items) => [
      ...items.map((item) => (item.streaming ? { ...item, streaming: false } : item)),
      userMessage,
      assistantMessage,
    ]);
    setPrompt('');

    try {
      let response: ChatResponse;
      if (existingSession) {
        const result = await session.callSession<ChatPayload, ChatResponse>(
          existingSession,
          'ai.chat',
          payload,
          CHAT_TIMEOUT_MS,
          (event) => handleChatEvent(event, assistantMessageId),
        );
        response = result.payload;
      } else {
        const result = await session.openJob<ChatPayload, ChatResponse>(
          'ai.chat',
          payload,
          CHAT_TIMEOUT_MS,
          (event) => handleChatEvent(event, assistantMessageId),
        );
        jobSessionRef.current = result.session;
        setJobSession(result.session);
        response = result.payload;
      }
      finishAssistant(assistantMessageId, response.answer);
      setContext(response);
    } catch (error) {
      finishAssistant(assistantMessageId, `Error: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setChatBusy(false);
    }
  }

  async function finishChatSession() {
    const currentSession = jobSessionRef.current;
    if (!currentSession || currentSession.closed) {
      jobSessionRef.current = null;
      setJobSession(null);
      return;
    }
    setChatBusy(true);
    try {
      await session.finishSession(currentSession, 'ai.chat', CHAT_TIMEOUT_MS);
    } catch {
      // The shared session hook records connection and job failures.
    } finally {
      jobSessionRef.current = null;
      setJobSession(null);
      setChatBusy(false);
    }
  }

  return (
    <section className="tabGrid workGrid">
      <div className="panel formPanel">
        <div className="panelHeader">
          <h2>ai.chat</h2>
          <MessageCircle size={17} aria-hidden="true" />
        </div>
        <label>
          <span>System Prompt</span>
          <textarea
            value={systemPrompt}
            onChange={(event) => setSystemPrompt(event.target.value)}
            rows={5}
            disabled={chatOpen}
          />
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
      </div>

      <div className="panel resultPanel">
        <div className="panelHeader">
          <h2>Conversation</h2>
          <span>{formatChatContext(context, chatOpen ? 'session open' : 'closed')}</span>
        </div>
        <div className="chatTranscript">
          {messages.map((item) => (
            <div key={item.id} className={`chatMessage ${item.role}`}>
              <div className={item.role === 'user' ? 'chatBubble' : 'chatMarkdown'}>
                <ReactMarkdown>{formatChatMarkdown(item.content || (item.streaming ? '...' : ''), item.role)}</ReactMarkdown>
              </div>
            </div>
          ))}
          {messages.length === 0 ? <p className="emptyText">No chat messages yet.</p> : null}
          <div ref={transcriptEndRef} />
        </div>
        <div className="chatComposer">
          <label>
            <span>Prompt</span>
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={4} />
          </label>
          <div className="chatComposerActions">
            <button
              type="button"
              className="primaryButton"
              onClick={() => {
                void callChat();
              }}
              disabled={session.busy || chatBusy}
            >
              <Send size={17} aria-hidden="true" />
              <span>Send</span>
            </button>
            <button
              type="button"
              onClick={() => {
                void finishChatSession();
              }}
              disabled={!chatOpen || chatBusy}
            >
              <Square size={16} aria-hidden="true" />
              <span>End Chat</span>
            </button>
          </div>
        </div>
      </div>
    </section>
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
  return `${usedTokens} / ${context.context_window} tokens, ${context.remaining_tokens} remaining, ${context.cache_enabled ? 'cache on' : 'cache off'}`;
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
    const nextCodeIndex =
      fenceIndex === -1 ? inlineIndex : inlineIndex === -1 ? fenceIndex : Math.min(fenceIndex, inlineIndex);
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
    } else {
      const inlineEnd = content.indexOf('`', nextCodeIndex + 1);
      const endIndex = inlineEnd === -1 ? content.length : inlineEnd + 1;
      formatted += content.slice(nextCodeIndex, endIndex);
      index = endIndex;
    }
  }
  return formatted;
}
