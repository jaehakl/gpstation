import {
  Brain,
  Cable,
  FileImage,
  Hash,
  ImageIcon,
  ListChecks,
  MessageCircle,
  RefreshCw,
  Send,
  Square,
  Wifi,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  GpStationClient,
  parseRtcIceServersJson,
} from '@gpstation/v1-master-js-sdk';
import ReactMarkdown from 'react-markdown';
import type {
  CandidateSummary,
  CallResult,
  ConnectDiagnosticEvent,
  JobEvent,
  JobDescriptor,
  JobSession,
  LauncherView,
  ReceivedFile,
} from '@gpstation/v1-master-js-sdk';

const defaultApiBaseUrl = import.meta.env.VITE_GPSTATION_V1_API_URL || '';
const defaultAccessToken = import.meta.env.VITE_GPSTATION_V1_ACCESS_TOKEN || '';
const defaultRtcIceServersJson = import.meta.env.VITE_GPSTATION_V1_RTC_ICE_SERVERS_JSON || '';
const LLM_TIMEOUT_MS = 600_000;
const CHAT_TIMEOUT_MS = 600_000;
const EMBEDDING_TIMEOUT_MS = 600_000;
const SDXL_TIMEOUT_MS = 600_000;

type TabId = 'connection' | 'llm' | 'chat' | 'embeddings' | 'sdxl';

type LogItem = {
  id: number;
  message: string;
};

type LlmResponse = {
  answer: string;
};

type ChatResponse = LlmResponse & {
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

type EmbeddingResponse = {
  embedding: number[];
  dimensions: number;
};

type SdxlImageMeta = {
  attachment_id: string;
  name: string;
  format: string;
  mimeType: string;
  size: number;
  seed: number;
};

type SdxlResponse = {
  images: SdxlImageMeta[];
  count: number;
};

type DisplayFile = ReceivedFile & {
  url: string;
  isImage: boolean;
  meta?: SdxlImageMeta;
};

type DiagnosticLogItem = ConnectDiagnosticEvent & {
  id: number;
  time: string;
};

const tabs: { id: TabId; label: string; icon: typeof Cable }[] = [
  { id: 'connection', label: 'Connection', icon: Cable },
  { id: 'llm', label: 'ai.llm', icon: Brain },
  { id: 'chat', label: 'ai.chat', icon: MessageCircle },
  { id: 'embeddings', label: 'ai.embeddings', icon: Hash },
  { id: 'sdxl', label: 'ai.sdxl.t2i', icon: ImageIcon },
];

export function App() {
  const [apiBaseUrl, setApiBaseUrl] = useState(defaultApiBaseUrl);
  const [token, setToken] = useState(defaultAccessToken);
  const [rtcIceServersJson, setRtcIceServersJson] = useState(defaultRtcIceServersJson);
  const [launchers, setLaunchers] = useState<LauncherView[]>([]);
  const [selectedLauncherId, setSelectedLauncherId] = useState('');
  const [currentJob, setCurrentJob] = useState<JobDescriptor | null>(null);
  const [status, setStatus] = useState('idle');
  const [activeTab, setActiveTab] = useState<TabId>('connection');
  const [busy, setBusy] = useState(false);
  const [logs, setLogs] = useState<LogItem[]>([]);
  const [diagnostics, setDiagnostics] = useState<DiagnosticLogItem[]>([]);
  const [localSdp, setLocalSdp] = useState('');
  const [remoteSdp, setRemoteSdp] = useState('');
  const [prewarmStatus, setPrewarmStatus] = useState('cold');

  const [llmSystemPrompt, setLlmSystemPrompt] = useState('You are a concise assistant.');
  const [llmPrompt, setLlmPrompt] = useState('Say hello from the AI slave.');
  const [llmMaxTokens, setLlmMaxTokens] = useState('512');
  const [llmTemperature, setLlmTemperature] = useState('0.5');
  const [llmResult, setLlmResult] = useState<LlmResponse | null>(null);
  const [llmRawJson, setLlmRawJson] = useState('');

  const [chatSystemPrompt, setChatSystemPrompt] = useState('You are a helpful conversational assistant.');
  const [chatPrompt, setChatPrompt] = useState('Say hello from the streaming chat handler.');
  const [chatMaxTokens, setChatMaxTokens] = useState('512');
  const [chatTemperature, setChatTemperature] = useState('0.5');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatContext, setChatContext] = useState<ChatResponse | null>(null);
  const [chatSession, setChatSession] = useState<JobSession | null>(null);
  const [chatSessionStatus, setChatSessionStatus] = useState('closed');
  const [chatBusy, setChatBusy] = useState(false);

  const [embeddingText, setEmbeddingText] = useState('GP Station AI slave embedding test');
  const [embeddingResult, setEmbeddingResult] = useState<EmbeddingResponse | null>(null);
  const [embeddingRawJson, setEmbeddingRawJson] = useState('');

  const [sdxlPrompts, setSdxlPrompts] = useState('a compact workstation on a clean desk');
  const [sdxlNegativePrompts, setSdxlNegativePrompts] = useState('');
  const [sdxlSeeds, setSdxlSeeds] = useState('123');
  const [sdxlStep, setSdxlStep] = useState('30');
  const [sdxlCfg, setSdxlCfg] = useState('7');
  const [sdxlWidth, setSdxlWidth] = useState('1024');
  const [sdxlHeight, setSdxlHeight] = useState('1024');
  const [sdxlFormat, setSdxlFormat] = useState('png');
  const [sdxlResult, setSdxlResult] = useState<SdxlResponse | null>(null);
  const [sdxlRawJson, setSdxlRawJson] = useState('');
  const [sdxlFiles, setSdxlFiles] = useState<DisplayFile[]>([]);

  const logIdRef = useRef(0);
  const diagnosticIdRef = useRef(0);
  const chatMessageIdRef = useRef(0);
  const activeChatAssistantMessageIdRef = useRef<number | null>(null);
  const chatTranscriptEndRef = useRef<HTMLDivElement | null>(null);
  const chatSessionRef = useRef<JobSession | null>(null);
  const sdxlFilesRef = useRef<DisplayFile[]>([]);

  const client = useMemo(
    () =>
      new GpStationClient({
        apiBaseUrl,
        token,
      }),
    [apiBaseUrl, token],
  );

  const selectedLauncher = launchers.find((launcher) => launcher.id === selectedLauncherId);
  const aiLaunchers = launchers.filter((launcher) => launcher.slave_app_ids.includes('ai'));
  const chatOpen = chatSession !== null && !chatSession.closed;

  const addLog = useCallback((message: string) => {
    const id = logIdRef.current + 1;
    logIdRef.current = id;
    setLogs((items) => [{ id, message }, ...items].slice(0, 16));
  }, []);

  const addDiagnostic = useCallback((event: ConnectDiagnosticEvent) => {
    const id = diagnosticIdRef.current + 1;
    diagnosticIdRef.current = id;
    if (event.localSdp) {
      setLocalSdp(event.localSdp);
    }
    if (event.remoteSdp) {
      setRemoteSdp(event.remoteSdp);
    }
    setDiagnostics((items) => [{ ...event, id, time: formatClock(new Date()) }, ...items].slice(0, 24));
  }, []);

  const prewarmAiConnection = useCallback(
    (logStart = false) => {
      if (!apiBaseUrl.trim() || !token.trim()) {
        setPrewarmStatus('waiting for server/token');
        return;
      }
      try {
        client.prewarmJobConnection({
          slaveAppId: 'ai',
          rtcConfig: parseRtcConfigInput(rtcIceServersJson),
          onDiagnostic: addDiagnostic,
        });
        setPrewarmStatus('network warm');
        if (logStart) {
          addLog('network prewarm started');
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setPrewarmStatus('prewarm failed');
        addLog(`network prewarm failed: ${message}`);
      }
    },
    [addDiagnostic, addLog, apiBaseUrl, client, rtcIceServersJson, token],
  );

  useEffect(() => {
    return () => {
      chatSessionRef.current?.close();
      revokeFiles(sdxlFilesRef.current);
    };
  }, []);

  useEffect(() => {
    chatSessionRef.current = chatSession;
  }, [chatSession]);

  useEffect(() => {
    chatTranscriptEndRef.current?.scrollIntoView({ block: 'end' });
  }, [chatMessages, chatBusy]);

  useEffect(() => {
    const session = chatSessionRef.current;
    if (session && !session.closed) {
      session.close();
      chatSessionRef.current = null;
      setChatSession(null);
      setChatSessionStatus('closed');
    }
  }, [client]);

  useEffect(() => {
    client.clearPrewarmedJobConnections();
    const timer = window.setTimeout(() => {
      prewarmAiConnection(true);
    }, 0);
    return () => {
      window.clearTimeout(timer);
      client.clearPrewarmedJobConnections();
    };
  }, [client, prewarmAiConnection]);

  function setNextSdxlFiles(files: DisplayFile[]) {
    revokeFiles(sdxlFilesRef.current);
    sdxlFilesRef.current = files;
    setSdxlFiles(files);
  }

  async function refreshLaunchers() {
    setBusy(true);
    try {
      const nextLaunchers = await client.listLaunchers();
      setLaunchers(nextLaunchers);
      const nextSelectedLauncher =
        nextLaunchers.find((launcher) => launcher.id === selectedLauncherId) ??
        nextLaunchers.find((launcher) => launcher.slave_app_ids.includes('ai')) ??
        nextLaunchers[0];
      if (nextSelectedLauncher) {
        setSelectedLauncherId(nextSelectedLauncher.id);
      }
      setStatus('launchers refreshed');
      addLog(`launchers: ${nextLaunchers.length} / ai-capable: ${nextLaunchers.filter((launcher) => launcher.slave_app_ids.includes('ai')).length}`);
    } catch (error) {
      handleError(error, 'launcher refresh failed');
    } finally {
      setBusy(false);
    }
  }

  function selectLauncher(launcher: LauncherView) {
    setSelectedLauncherId(launcher.id);
  }

  function setCurrentJobState(state: string) {
    setCurrentJob((job) => (job ? { ...job, state } : job));
  }

  async function runAiJob<TPayload, TResult>(
    handlerType: string,
    payload: TPayload,
    timeoutMs: number,
  ): Promise<CallResult<TResult>> {
    setDiagnostics([]);
    setLocalSdp('');
    setRemoteSdp('');
    setCurrentJob(null);
    try {
      return await client.runJob<TPayload, TResult>(handlerType, payload, {
        slaveAppId: 'ai',
        timeoutMs,
        rtcConfig: parseRtcConfigInput(rtcIceServersJson),
        onJobCreated: (job) => {
          setCurrentJob(job);
          addLog(`job: ${job.id}`);
        },
        onStatus: (nextStatus) => {
          setStatus(nextStatus);
          if (nextStatus === 'waiting for answer') {
            setCurrentJobState('assigned');
          }
          if (nextStatus === 'waiting for data channel') {
            setCurrentJobState('answer_ready');
          }
          if (nextStatus === 'waiting for result') {
            setCurrentJobState('running');
          }
          addLog(nextStatus);
        },
        onDiagnostic: addDiagnostic,
      });
    } finally {
      prewarmAiConnection();
    }
  }

  async function callLlm() {
    const payload = {
      system_prompt: llmSystemPrompt,
      prompt: llmPrompt,
      max_tokens: parseOptionalInt(llmMaxTokens, 'max tokens'),
      temperature: parseOptionalFloat(llmTemperature, 'temperature'),
    };
    const startedAt = new Date();
    setBusy(true);
    addLog(`${formatClock(new Date())} ai.llm start`);
    try {
      const result = await runAiJob<typeof payload, LlmResponse>('ai.llm', payload, LLM_TIMEOUT_MS);
      setLlmResult(result.payload);
      setLlmRawJson(formatJson(result.payload));
      setCurrentJobState('succeeded');
      setStatus('ai.llm complete');
      addLog(`${formatClock(new Date())} ai.llm complete (${formatDurationSince(startedAt)})`);
    } catch (error) {
      setCurrentJobState('failed');
      addLog(`${formatClock(new Date())} ai.llm failed (${formatDurationSince(startedAt)})`);
      handleError(error, 'ai.llm failed');
    } finally {
      setBusy(false);
    }
  }

  function nextChatMessageId(): number {
    const id = chatMessageIdRef.current + 1;
    chatMessageIdRef.current = id;
    return id;
  }

  function appendChatDelta(messageId: number, delta: string) {
    if (activeChatAssistantMessageIdRef.current !== messageId) {
      return;
    }
    setChatMessages((items) =>
      items.map((item) =>
        item.id === messageId && item.streaming ? { ...item, content: item.content + delta } : item,
      ),
    );
  }

  function finishChatAssistant(messageId: number, answer: string) {
    setChatMessages((items) =>
      items.map((item) => (item.id === messageId ? { ...item, content: answer, streaming: false } : item)),
    );
    if (activeChatAssistantMessageIdRef.current === messageId) {
      activeChatAssistantMessageIdRef.current = null;
    }
  }

  function handleChatEvent(event: JobEvent, assistantMessageId: number) {
    if (activeChatAssistantMessageIdRef.current !== assistantMessageId) {
      return;
    }
    if (event.type !== 'ai.chat.delta') {
      return;
    }
    const delta = readChatDelta(event.payload);
    if (delta) {
      appendChatDelta(assistantMessageId, delta);
    }
  }

  async function callChat() {
    const prompt = chatPrompt.trim();
    if (!prompt) {
      handleError(new Error('prompt is required'), 'ai.chat failed');
      return;
    }
    const existingSession = chatSessionRef.current && !chatSessionRef.current.closed ? chatSessionRef.current : null;
    const systemPrompt = chatSystemPrompt.trim();
    if (!existingSession && !systemPrompt) {
      handleError(new Error('system prompt is required for a new chat'), 'ai.chat failed');
      return;
    }
    let payload: ChatPayload;
    try {
      payload = {
        prompt,
        max_tokens: parseOptionalInt(chatMaxTokens, 'max tokens'),
        temperature: parseOptionalFloat(chatTemperature, 'temperature'),
      };
    } catch (error) {
      handleError(error, 'ai.chat failed');
      return;
    }
    if (!existingSession) {
      payload.system_prompt = systemPrompt;
    }

    const userMessage: ChatMessage = {
      id: nextChatMessageId(),
      role: 'user',
      content: prompt,
      streaming: false,
    };
    const assistantMessageId = nextChatMessageId();
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      streaming: true,
    };

    const startedAt = new Date();
    activeChatAssistantMessageIdRef.current = assistantMessageId;
    setBusy(true);
    setChatBusy(true);
    setChatMessages((items) => [
      ...items.map((item) => (item.streaming ? { ...item, streaming: false } : item)),
      userMessage,
      assistantMessage,
    ]);
    setChatPrompt('');
    addLog(`${formatClock(new Date())} ai.chat start`);
    try {
      let response: ChatResponse;
      if (existingSession) {
        setStatus('ai.chat waiting for result');
        setCurrentJobState('running');
        const result = await existingSession.call<ChatPayload, ChatResponse>('ai.chat', payload, {
          timeoutMs: CHAT_TIMEOUT_MS,
          onEvent: (event) => handleChatEvent(event, assistantMessageId),
        });
        response = result.payload;
      } else {
        setDiagnostics([]);
        setLocalSdp('');
        setRemoteSdp('');
        setCurrentJob(null);
        const result = await client.runJob<ChatPayload, ChatResponse>('ai.chat', payload, {
          slaveAppId: 'ai',
          timeoutMs: CHAT_TIMEOUT_MS,
          autoFinish: false,
          rtcConfig: parseRtcConfigInput(rtcIceServersJson),
          onEvent: (event) => handleChatEvent(event, assistantMessageId),
          onJobCreated: (job) => {
            setCurrentJob(job);
            addLog(`job: ${job.id}`);
          },
          onStatus: (nextStatus) => {
            setStatus(nextStatus);
            if (nextStatus === 'waiting for answer') {
              setCurrentJobState('assigned');
            }
            if (nextStatus === 'waiting for data channel') {
              setCurrentJobState('answer_ready');
            }
            if (nextStatus === 'waiting for result') {
              setCurrentJobState('running');
            }
            addLog(nextStatus);
          },
          onDiagnostic: addDiagnostic,
        });
        response = result.payload;
        chatSessionRef.current = result.session;
        setChatSession(result.session);
        setChatSessionStatus('open');
      }
      finishChatAssistant(assistantMessageId, response.answer);
      setChatContext(response);
      setCurrentJobState('running');
      setStatus('ai.chat response complete');
      addLog(`${formatClock(new Date())} ai.chat response complete (${formatDurationSince(startedAt)})`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      finishChatAssistant(assistantMessageId, `Error: ${message}`);
      setCurrentJobState('failed');
      addLog(`${formatClock(new Date())} ai.chat failed (${formatDurationSince(startedAt)})`);
      handleError(error, 'ai.chat failed');
    } finally {
      setBusy(false);
      setChatBusy(false);
    }
  }

  async function finishChatSession() {
    const session = chatSessionRef.current;
    if (!session || session.closed) {
      chatSessionRef.current = null;
      setChatSession(null);
      setChatSessionStatus('closed');
      return;
    }
    const startedAt = new Date();
    setBusy(true);
    setChatBusy(true);
    addLog(`${formatClock(new Date())} ai.chat finish`);
    try {
      await session.finish({ timeoutMs: CHAT_TIMEOUT_MS });
      setCurrentJobState('succeeded');
      setStatus('ai.chat session closed');
      addLog(`${formatClock(new Date())} ai.chat session closed (${formatDurationSince(startedAt)})`);
    } catch (error) {
      session.close();
      setCurrentJobState('failed');
      addLog(`${formatClock(new Date())} ai.chat finish failed (${formatDurationSince(startedAt)})`);
      handleError(error, 'ai.chat finish failed');
    } finally {
      chatSessionRef.current = null;
      setChatSession(null);
      setChatSessionStatus('closed');
      setBusy(false);
      setChatBusy(false);
      prewarmAiConnection();
    }
  }

  async function callEmbeddings() {
    const payload = {
      text: embeddingText,
    };
    const startedAt = new Date();
    setBusy(true);
    addLog(`${formatClock(new Date())} ai.embeddings start`);
    try {
      const result = await runAiJob<typeof payload, EmbeddingResponse>('ai.embeddings', payload, EMBEDDING_TIMEOUT_MS);
      setEmbeddingResult(result.payload);
      setEmbeddingRawJson(formatJson(result.payload));
      setCurrentJobState('succeeded');
      setStatus('ai.embeddings complete');
      addLog(`${formatClock(new Date())} ai.embeddings complete (${formatDurationSince(startedAt)})`);
    } catch (error) {
      setCurrentJobState('failed');
      addLog(`${formatClock(new Date())} ai.embeddings failed (${formatDurationSince(startedAt)})`);
      handleError(error, 'ai.embeddings failed');
    } finally {
      setBusy(false);
    }
  }

  async function callSdxl() {
    const payload = buildSdxlPayload({
      prompts: sdxlPrompts,
      negativePrompts: sdxlNegativePrompts,
      seeds: sdxlSeeds,
      step: sdxlStep,
      cfg: sdxlCfg,
      width: sdxlWidth,
      height: sdxlHeight,
      format: sdxlFormat,
    });
    const startedAt = new Date();
    setBusy(true);
    setNextSdxlFiles([]);
    addLog(`${formatClock(new Date())} ai.sdxl.t2i start`);
    try {
      const result = await runAiJob<typeof payload, SdxlResponse>('ai.sdxl.t2i', payload, SDXL_TIMEOUT_MS);
      const payloadImages = result.payload.images ?? [];
      const metaByAttachmentId = new Map(payloadImages.map((image) => [image.attachment_id, image]));
      const nextFiles = result.files.map((file) => ({
        ...file,
        url: URL.createObjectURL(file.blob),
        isImage: Boolean(file.mimeType?.startsWith('image/')),
        meta: metaByAttachmentId.get(file.id),
      }));
      setSdxlResult(result.payload);
      setSdxlRawJson(formatJson(result.payload));
      setNextSdxlFiles(nextFiles);
      setCurrentJobState('succeeded');
      setStatus('ai.sdxl.t2i complete');
      addLog(
        `${formatClock(new Date())} ai.sdxl.t2i complete (${formatDurationSince(startedAt)}): ${nextFiles.length} file(s)`,
      );
    } catch (error) {
      setCurrentJobState('failed');
      addLog(`${formatClock(new Date())} ai.sdxl.t2i failed (${formatDurationSince(startedAt)})`);
      handleError(error, 'ai.sdxl.t2i failed');
    } finally {
      setBusy(false);
    }
  }

  function handleError(error: unknown, nextStatus: string) {
    const message = error instanceof Error ? error.message : String(error);
    setStatus(nextStatus);
    addLog(message);
  }

  return (
    <main className="shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">GP Station v1</p>
          <h1>AI Master Console</h1>
        </div>
        <div className={busy ? 'statusPill connected' : 'statusPill'}>
          <Wifi size={16} aria-hidden="true" />
          <span>{status}</span>
        </div>
      </section>

      <section className="controlBand">
        <label>
          <span>Server</span>
          <input value={apiBaseUrl} onChange={(event) => setApiBaseUrl(event.target.value)} />
        </label>
        <label>
          <span>Token</span>
          <input value={token} onChange={(event) => setToken(event.target.value)} />
        </label>
        <label>
          <span>ICE Servers JSON</span>
          <textarea
            className="compactTextarea"
            value={rtcIceServersJson}
            onChange={(event) => setRtcIceServersJson(event.target.value)}
            rows={3}
            placeholder='[{"urls":"stun:stun.l.google.com:19302"}]'
          />
        </label>
        <label>
          <span>AI Launcher Reference</span>
          <select
            value={selectedLauncherId}
            onChange={(event) => {
              const launcher = launchers.find((item) => item.id === event.target.value);
              if (launcher) {
                selectLauncher(launcher);
              } else {
                setSelectedLauncherId('');
              }
            }}
          >
            <option value="">No launcher selected</option>
            {aiLaunchers.map((launcher) => (
              <option key={launcher.id} value={launcher.id}>
                {launcher.launcher_name} | {launcher.status} | {launcher.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
        <div className="buttonCluster">
          <button type="button" onClick={refreshLaunchers} disabled={busy} title="Refresh launchers">
            <RefreshCw size={17} aria-hidden="true" />
            <span>Refresh</span>
          </button>
        </div>
      </section>

      <nav className="tabBar" aria-label="AI test sections">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              type="button"
              key={tab.id}
              className={activeTab === tab.id ? 'tabButton active' : 'tabButton'}
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon size={17} aria-hidden="true" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>

      {activeTab === 'connection' && (
        <section className="tabGrid connectionGrid">
          <div className="panel">
            <div className="panelHeader">
              <h2>Launchers</h2>
              <span>{launchers.length}</span>
            </div>
            <div className="table">
              <div className="tableHead">
                <span>Name</span>
                <span>Status</span>
                <span>Apps</span>
              </div>
              {launchers.map((launcher) => (
                <button
                  type="button"
                  key={launcher.id}
                  className={launcher.id === selectedLauncherId ? 'launcherRow selected' : 'launcherRow'}
                  onClick={() => selectLauncher(launcher)}
                >
                  <span>{launcher.launcher_name}</span>
                  <span>{launcher.status}</span>
                  <span>{launcher.slave_app_ids.join(', ') || '-'}</span>
                </button>
              ))}
              {launchers.length === 0 && <p className="emptyText">No connected launchers.</p>}
            </div>
          </div>

          <div className="sideStack">
            <div className="panel">
              <div className="panelHeader">
                <h2>Job</h2>
                <ListChecks size={17} aria-hidden="true" />
              </div>
              <dl className="details">
                <div>
                  <dt>Job ID</dt>
                  <dd>{currentJob?.id || '-'}</dd>
                </div>
                <div>
                  <dt>Assigned Launcher</dt>
                  <dd>{currentJob?.launcher_id || '-'}</dd>
                </div>
                <div>
                  <dt>Slave App</dt>
                  <dd>{currentJob?.slave_app_id || 'ai'}</dd>
                </div>
                <div>
                  <dt>State</dt>
                  <dd>{currentJob?.state || 'idle'}</dd>
                </div>
                <div>
                  <dt>Network Prewarm</dt>
                  <dd>{prewarmStatus}</dd>
                </div>
                <div>
                  <dt>Reference Launcher</dt>
                  <dd>{selectedLauncher?.launcher_name || '-'}</dd>
                </div>
              </dl>
            </div>

            <div className="panel">
              <div className="panelHeader">
                <h2>Log</h2>
                <ListChecks size={17} aria-hidden="true" />
              </div>
              <ol className="logList">
                {logs.map((item) => (
                  <li key={item.id}>{item.message}</li>
                ))}
                {logs.length === 0 && <li>Ready.</li>}
              </ol>
            </div>

            <div className="panel diagnosticPanel">
              <div className="panelHeader">
                <h2>WebRTC Diagnostics</h2>
                <Cable size={17} aria-hidden="true" />
              </div>
              <ol className="logList diagnosticList">
                {diagnostics.map((item) => (
                  <li key={item.id}>
                    <strong>{item.time}</strong> {item.message}
                    <span>{formatDiagnosticState(item)}</span>
                    {(item.prewarmHit !== undefined ||
                      item.offerGatheringMs !== undefined ||
                      item.answerWaitMs !== undefined ||
                      item.dataChannelOpenMs !== undefined ||
                      item.elapsedMs !== undefined) && (
                      <span>
                        {[
                          item.prewarmHit !== undefined ? `prewarm=${item.prewarmHit ? 'hit' : 'miss'}` : '',
                          item.offerGatheringMs !== undefined ? `offer=${formatDuration(item.offerGatheringMs)}` : '',
                          item.answerWaitMs !== undefined ? `answer=${formatDuration(item.answerWaitMs)}` : '',
                          item.dataChannelOpenMs !== undefined ? `datachannel=${formatDuration(item.dataChannelOpenMs)}` : '',
                          item.elapsedMs !== undefined ? `elapsed=${formatDuration(item.elapsedMs)}` : '',
                        ]
                          .filter(Boolean)
                          .join(' / ')}
                      </span>
                    )}
                    {item.localCandidateSummary && <span>local: {formatCandidateSummary(item.localCandidateSummary)}</span>}
                    {item.remoteCandidateSummary && <span>remote: {formatCandidateSummary(item.remoteCandidateSummary)}</span>}
                  </li>
                ))}
                {diagnostics.length === 0 && <li>No WebRTC diagnostics yet.</li>}
              </ol>
              <details className="sdpDetails">
                <summary>Local offer SDP</summary>
                <pre className="sdpBox">{localSdp || 'No local offer yet.'}</pre>
              </details>
              <details className="sdpDetails">
                <summary>Remote answer SDP</summary>
                <pre className="sdpBox">{remoteSdp || 'No remote answer yet.'}</pre>
              </details>
            </div>
          </div>
        </section>
      )}

      {activeTab === 'llm' && (
        <section className="tabGrid workGrid">
          <div className="panel formPanel">
            <div className="panelHeader">
              <h2>ai.llm</h2>
              <Brain size={17} aria-hidden="true" />
            </div>
            <label>
              <span>System Prompt</span>
              <textarea value={llmSystemPrompt} onChange={(event) => setLlmSystemPrompt(event.target.value)} rows={5} />
            </label>
            <label>
              <span>Prompt</span>
              <textarea value={llmPrompt} onChange={(event) => setLlmPrompt(event.target.value)} rows={7} />
            </label>
            <div className="formGrid compact">
              <label>
                <span>Max Tokens</span>
                <input value={llmMaxTokens} inputMode="numeric" onChange={(event) => setLlmMaxTokens(event.target.value)} />
              </label>
              <label>
                <span>Temperature</span>
                <input value={llmTemperature} inputMode="decimal" onChange={(event) => setLlmTemperature(event.target.value)} />
              </label>
            </div>
            <button type="button" className="primaryButton" onClick={callLlm} disabled={busy}>
              <Send size={17} aria-hidden="true" />
              <span>Send</span>
            </button>
          </div>

          <div className="panel resultPanel">
            <div className="panelHeader">
              <h2>Output</h2>
              <span>{llmResult ? 'ready' : 'empty'}</span>
            </div>
            <pre className="answerBox">{llmResult?.answer || 'No answer yet.'}</pre>
            <pre className="resultBox">{llmRawJson || 'No raw result yet.'}</pre>
          </div>
        </section>
      )}

      {activeTab === 'chat' && (
        <section className="tabGrid workGrid">
          <div className="panel formPanel">
            <div className="panelHeader">
              <h2>ai.chat</h2>
              <MessageCircle size={17} aria-hidden="true" />
            </div>
            <label>
              <span>System Prompt</span>
              <textarea
                value={chatSystemPrompt}
                onChange={(event) => setChatSystemPrompt(event.target.value)}
                rows={5}
                disabled={chatOpen}
              />
            </label>
            <div className="formGrid compact">
              <label>
                <span>Max Tokens</span>
                <input value={chatMaxTokens} inputMode="numeric" onChange={(event) => setChatMaxTokens(event.target.value)} />
              </label>
              <label>
                <span>Temperature</span>
                <input value={chatTemperature} inputMode="decimal" onChange={(event) => setChatTemperature(event.target.value)} />
              </label>
            </div>
          </div>

          <div className="panel resultPanel">
            <div className="panelHeader">
              <h2>Conversation</h2>
              <span>{formatChatContext(chatContext, chatOpen ? 'session open' : chatSessionStatus)}</span>
            </div>
            <div className="chatTranscript">
              {chatMessages.map((item) => (
                <div key={item.id} className={`chatMessage ${item.role}`}>
                  <div className={item.role === 'user' ? 'chatBubble' : 'chatMarkdown'}>
                    <ReactMarkdown>{formatChatMarkdown(item.content || (item.streaming ? '...' : ''), item.role)}</ReactMarkdown>
                  </div>
                </div>
              ))}
              {chatMessages.length === 0 && <p className="emptyText">No chat messages yet.</p>}
              <div ref={chatTranscriptEndRef} />
            </div>
            <div className="chatComposer">
              <label>
                <span>Prompt</span>
                <textarea value={chatPrompt} onChange={(event) => setChatPrompt(event.target.value)} rows={4} />
              </label>
              <div className="chatComposerActions">
                <button type="button" className="primaryButton" onClick={callChat} disabled={busy || chatBusy}>
                  <Send size={17} aria-hidden="true" />
                  <span>Send</span>
                </button>
                <button type="button" onClick={finishChatSession} disabled={!chatOpen || chatBusy}>
                  <Square size={16} aria-hidden="true" />
                  <span>End Chat</span>
                </button>
              </div>
            </div>
          </div>
        </section>
      )}

      {activeTab === 'embeddings' && (
        <section className="tabGrid workGrid">
          <div className="panel formPanel">
            <div className="panelHeader">
              <h2>ai.embeddings</h2>
              <Hash size={17} aria-hidden="true" />
            </div>
            <label>
              <span>Text</span>
              <textarea value={embeddingText} onChange={(event) => setEmbeddingText(event.target.value)} rows={10} />
            </label>
            <button type="button" className="primaryButton" onClick={callEmbeddings} disabled={busy}>
              <Send size={17} aria-hidden="true" />
              <span>Send</span>
            </button>
          </div>

          <div className="panel resultPanel">
            <div className="panelHeader">
              <h2>Output</h2>
              <span>{embeddingResult ? `${embeddingResult.dimensions} dims` : 'empty'}</span>
            </div>
            <div className="metricStrip">
              <div>
                <span>Dimensions</span>
                <strong>{embeddingResult?.dimensions ?? '-'}</strong>
              </div>
              <div>
                <span>Preview</span>
                <strong>{embeddingResult ? vectorPreview(embeddingResult.embedding) : '-'}</strong>
              </div>
            </div>
            <pre className="resultBox">{embeddingRawJson || 'No raw result yet.'}</pre>
          </div>
        </section>
      )}

      {activeTab === 'sdxl' && (
        <section className="tabGrid sdxlGrid">
          <div className="panel formPanel">
            <div className="panelHeader">
              <h2>ai.sdxl.t2i</h2>
              <ImageIcon size={17} aria-hidden="true" />
            </div>
            <label>
              <span>Prompts</span>
              <textarea value={sdxlPrompts} onChange={(event) => setSdxlPrompts(event.target.value)} rows={5} />
            </label>
            <label>
              <span>Negative Prompts</span>
              <textarea value={sdxlNegativePrompts} onChange={(event) => setSdxlNegativePrompts(event.target.value)} rows={4} />
            </label>
            <div className="formGrid compact">
              <label>
                <span>Seeds</span>
                <input value={sdxlSeeds} onChange={(event) => setSdxlSeeds(event.target.value)} />
              </label>
              <label>
                <span>Format</span>
                <select value={sdxlFormat} onChange={(event) => setSdxlFormat(event.target.value)}>
                  <option value="png">png</option>
                  <option value="jpg">jpg</option>
                </select>
              </label>
              <label>
                <span>Step</span>
                <input value={sdxlStep} inputMode="numeric" onChange={(event) => setSdxlStep(event.target.value)} />
              </label>
              <label>
                <span>CFG</span>
                <input value={sdxlCfg} inputMode="decimal" onChange={(event) => setSdxlCfg(event.target.value)} />
              </label>
              <label>
                <span>Width</span>
                <input value={sdxlWidth} inputMode="numeric" onChange={(event) => setSdxlWidth(event.target.value)} />
              </label>
              <label>
                <span>Height</span>
                <input value={sdxlHeight} inputMode="numeric" onChange={(event) => setSdxlHeight(event.target.value)} />
              </label>
            </div>
            <button type="button" className="primaryButton" onClick={callSdxl} disabled={busy}>
              <Send size={17} aria-hidden="true" />
              <span>Send</span>
            </button>
          </div>

          <div className="panel resultPanel">
            <div className="panelHeader">
              <h2>Output</h2>
              <span>{sdxlResult ? `${sdxlResult.count} image(s)` : 'empty'}</span>
            </div>
            <pre className="resultBox">{sdxlRawJson || 'No metadata yet.'}</pre>
            <div className="imageResults">
              {sdxlFiles.map((file) => (
                <a key={file.id} className="imageResult" href={file.url} download={file.name || file.id}>
                  {file.isImage ? <img src={file.url} alt={file.name || file.id} /> : <FileImage size={40} aria-hidden="true" />}
                  <span>{file.meta?.name || file.name || file.id}</span>
                  <span>
                    {file.meta ? `seed ${file.meta.seed} | ` : ''}
                    {formatBytes(file.size)}
                  </span>
                </a>
              ))}
              {sdxlFiles.length === 0 && <p className="emptyText">No image attachments yet.</p>}
            </div>
          </div>
        </section>
      )}
    </main>
  );
}

function parseRtcConfigInput(value: string): RTCConfiguration | undefined {
  const trimmed = value.trim();
  return trimmed ? { iceServers: parseRtcIceServersJson(trimmed) } : undefined;
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

function parseRequiredInt(value: string, label: string): number {
  const parsed = parseOptionalInt(value, label);
  if (parsed === undefined) {
    throw new Error(`${label} is required`);
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

function parseRequiredFloat(value: string, label: string): number {
  const parsed = parseOptionalFloat(value, label);
  if (parsed === undefined) {
    throw new Error(`${label} is required`);
  }
  return parsed;
}

function parseLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseOptionalSeedList(value: string): (number | null)[] | undefined {
  const items = value
    .split(/[\r\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  if (items.length === 0) {
    return undefined;
  }
  return items.map((item) => {
    if (item.toLowerCase() === 'null') {
      return null;
    }
    const parsed = Number(item);
    if (!Number.isInteger(parsed)) {
      throw new Error('seeds must be integers or null');
    }
    return parsed;
  });
}

function buildSdxlPayload(input: {
  prompts: string;
  negativePrompts: string;
  seeds: string;
  step: string;
  cfg: string;
  width: string;
  height: string;
  format: string;
}) {
  const prompts = parseLines(input.prompts);
  if (prompts.length === 0) {
    throw new Error('prompts is required');
  }
  const negativePrompts = parseLines(input.negativePrompts);
  const seeds = parseOptionalSeedList(input.seeds);
  return {
    prompts,
    negative_prompts: negativePrompts.length > 0 ? negativePrompts : undefined,
    seeds,
    step: parseRequiredInt(input.step, 'step'),
    cfg: parseRequiredFloat(input.cfg, 'cfg'),
    width: parseRequiredInt(input.width, 'width'),
    height: parseRequiredInt(input.height, 'height'),
    format: input.format,
  };
}

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function formatClock(value: Date): string {
  return value.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${Math.round(ms)}ms`;
  }
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatDurationSince(startedAt: Date): string {
  return formatDuration(new Date().getTime() - startedAt.getTime());
}

function formatCandidateSummary(summary: CandidateSummary): string {
  return `total=${summary.total} host=${summary.host} srflx=${summary.srflx} relay=${summary.relay} prflx=${summary.prflx} unknown=${summary.unknown}`;
}

function formatDiagnosticState(event: ConnectDiagnosticEvent): string {
  return [
    `signaling=${event.signalingState ?? '-'}`,
    `iceGathering=${event.iceGatheringState ?? '-'}`,
    `iceConnection=${event.iceConnectionState ?? '-'}`,
    `connection=${event.connectionState ?? '-'}`,
    `dataChannel=${event.dataChannelState ?? '-'}`,
  ].join(' / ');
}

function vectorPreview(values: number[]): string {
  return values
    .slice(0, 8)
    .map((value) => Number(value).toFixed(4))
    .join(', ');
}

function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function revokeFiles(files: DisplayFile[]) {
  for (const file of files) {
    URL.revokeObjectURL(file.url);
  }
}
