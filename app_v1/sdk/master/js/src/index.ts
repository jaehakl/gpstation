export type LauncherView = {
  id: string;
  user_id: string;
  launcher_name: string;
  status: string;
  slave_app_ids: string[];
  connected_at: string;
  last_heartbeat_at: string;
};

export type JobDescriptor = {
  id: string;
  user_id: string;
  handler_type: string;
  slave_app_id: string;
  offer: SignalPayload;
  answer?: SignalPayload | null;
  progress: unknown[];
  state: string;
  launcher_id?: string | null;
};

export type JobCreateResult = {
  job: JobDescriptor;
  answer_wait_url: string;
};

export type JobAnswerWaitResult = {
  job_id: string;
  state: string;
  answer?: SignalPayload | null;
  last_error?: string | null;
};

export type SignalPayload =
  | { type: 'offer'; sdp: string }
  | { type: 'answer'; sdp: string }
  | { type: 'ice'; candidate?: string; sdpMid?: string; sdpMLineIndex?: number }
  | { type: 'end-of-candidates' };

export type AttachmentMetadata = {
  id: string;
  name?: string;
  mimeType?: string;
  size: number;
};

export type CallResponseFrame<T = unknown> = {
  kind: 'call.response';
  id: string;
  type: string;
  payload?: T;
  attachments: AttachmentMetadata[];
};

export type CallErrorFrame = {
  kind: 'call.error';
  id: string;
  code?: string;
  detail: string;
};

export type AttachmentChunkHeader = {
  kind: 'attachment.chunk';
  callId: string;
  attachmentId: string;
  index: number;
  final: boolean;
};

export type ReceivedFile = AttachmentMetadata & {
  blob: Blob;
};

export type CallResult<T = unknown> = {
  payload: T;
  files: ReceivedFile[];
};

export type CandidateSummary = {
  host: number;
  srflx: number;
  relay: number;
  prflx: number;
  unknown: number;
  total: number;
};

export type ConnectDiagnosticEvent = {
  stage: string;
  message: string;
  elapsedMs?: number;
  stageStartedAt?: number;
  prewarmHit?: boolean;
  offerGatheringMs?: number;
  answerWaitMs?: number;
  dataChannelOpenMs?: number;
  signalingState?: RTCSignalingState;
  iceGatheringState?: RTCIceGatheringState;
  iceConnectionState?: RTCIceConnectionState;
  connectionState?: RTCPeerConnectionState;
  dataChannelState?: RTCDataChannelState;
  localCandidateSummary?: CandidateSummary;
  remoteCandidateSummary?: CandidateSummary;
  localSdp?: string;
  remoteSdp?: string;
};

export type GpStationClientOptions = {
  apiBaseUrl: string;
  token: string;
  rtcConfig?: RTCConfiguration;
};

export type ConnectOptions = {
  timeoutMs?: number;
  onStatus?: (status: string) => void;
  onDiagnostic?: (event: ConnectDiagnosticEvent) => void;
};

export type RunJobOptions = ConnectOptions & {
  slaveAppId?: string;
  rtcConfig?: RTCConfiguration;
  onJobCreated?: (job: JobDescriptor) => void;
};

export type JobConnectionPrewarmOptions = {
  slaveAppId?: string;
  rtcConfig?: RTCConfiguration;
  onDiagnostic?: (event: ConnectDiagnosticEvent) => void;
};

type IncomingFile = AttachmentMetadata & {
  chunks: Uint8Array[];
  receivedSize: number;
  nextIndex: number;
  complete: boolean;
};

type PendingResponse = {
  id?: string;
  payload: unknown;
  attachments: AttachmentMetadata[];
  files: Map<string, IncomingFile>;
};

type PreparedJobConnection = {
  peerConnection: RTCPeerConnection;
  dataChannel: RTCDataChannel;
  key: string;
  slaveAppId: string;
  rtcConfig: RTCConfiguration;
  diagnosticsRegistered: boolean;
};

class RunJobAttemptError extends Error {
  constructor(
    message: string,
    readonly jobId: string | undefined,
    readonly inputSent: boolean,
  ) {
    super(message);
    this.name = 'RunJobAttemptError';
  }
}

export const DEFAULT_RTC_ICE_SERVERS: RTCIceServer[] = [{ urls: 'stun:stun.l.google.com:19302' }];
export const DEFAULT_RTC_ICE_CANDIDATE_POOL_SIZE = 2;
const textDecoder = new TextDecoder();

export class GpStationClient {
  private readonly apiBaseUrl: string;
  private readonly token: string;
  private readonly rtcConfig?: RTCConfiguration;
  private readonly prewarmedJobConnections: PreparedJobConnection[] = [];

  constructor(options: GpStationClientOptions) {
    this.apiBaseUrl = options.apiBaseUrl.replace(/\/+$/, '');
    this.token = options.token;
    this.rtcConfig = options.rtcConfig;
  }

  async listLaunchers(): Promise<LauncherView[]> {
    return this.request<LauncherView[]>('/v1/launchers');
  }

  prewarmJobConnection(options: JobConnectionPrewarmOptions = {}): void {
    const slaveAppId = options.slaveAppId ?? 'ai';
    const rtcConfig = rtcConfigWithDefaults(options.rtcConfig ?? this.rtcConfig);
    const key = jobConnectionKey(slaveAppId, rtcConfig);
    this.dropClosedPrewarmedJobConnections();
    if (this.prewarmedJobConnections.some((item) => item.key === key)) {
      return;
    }
    const prepared = createPreparedJobConnection(slaveAppId, rtcConfig);
    const diagnostic = options.onDiagnostic ?? (() => undefined);
    emitDiagnostic(prepared.peerConnection, prepared.dataChannel, diagnostic, {
      stage: 'job-prewarm',
      message: 'job prewarm refreshed',
      elapsedMs: 0,
      stageStartedAt: Date.now(),
    });
    this.prewarmedJobConnections.push(prepared);
  }

  clearPrewarmedJobConnections(): void {
    for (const item of this.prewarmedJobConnections.splice(0)) {
      item.peerConnection.close();
    }
  }

  async runJob<TInput = unknown, TResult = unknown>(
    handlerType: string,
    input?: TInput,
    options: RunJobOptions = {},
  ): Promise<CallResult<TResult>> {
    const status = options.onStatus ?? (() => undefined);
    const diagnostic = options.onDiagnostic ?? (() => undefined);
    const timeoutMs = options.timeoutMs ?? 60000;
    const slaveAppId = options.slaveAppId ?? 'ai';
    const rtcConfig = rtcConfigWithDefaults(options.rtcConfig ?? this.rtcConfig);
    try {
      return await this.runJobAttempt<TInput, TResult>({
        handlerType,
        input,
        options,
        status,
        diagnostic,
        timeoutMs,
        slaveAppId,
        rtcConfig,
        attempt: 0,
      });
    } catch (error) {
      const attemptError =
        error instanceof RunJobAttemptError
          ? error
          : new RunJobAttemptError(error instanceof Error ? error.message : String(error), undefined, false);
      if (attemptError.inputSent) {
        diagnostic({
          stage: 'job-retry',
          message: 'retry skipped after input sent',
        });
        throw attemptError;
      }
      diagnostic({
        stage: 'job-retry',
        message: 'retry attempt=1',
        elapsedMs: 0,
      });
      await this.killJobBestEffort(attemptError.jobId);
      return await this.runJobAttempt<TInput, TResult>({
        handlerType,
        input,
        options,
        status,
        diagnostic,
        timeoutMs,
        slaveAppId,
        rtcConfig,
        attempt: 1,
      });
    } finally {
      this.prewarmJobConnection({ slaveAppId, rtcConfig, onDiagnostic: diagnostic });
    }
  }

  private async runJobAttempt<TInput = unknown, TResult = unknown>(params: {
    handlerType: string;
    input?: TInput;
    options: RunJobOptions;
    status: (status: string) => void;
    diagnostic: (event: ConnectDiagnosticEvent) => void;
    timeoutMs: number;
    slaveAppId: string;
    rtcConfig: RTCConfiguration;
    attempt: number;
  }): Promise<CallResult<TResult>> {
    const { handlerType, input, options, status, diagnostic, timeoutMs, slaveAppId, rtcConfig, attempt } = params;
    const prepared = this.takePrewarmedJobConnection(slaveAppId, rtcConfig);
    const prewarmHit = prepared !== undefined;
    const peerConnection = prepared?.peerConnection ?? new RTCPeerConnection(rtcConfig);
    const dataChannel = prepared?.dataChannel ?? peerConnection.createDataChannel('gpstation.v1', { ordered: true });
    const jobPeer = new GpStationJobPeer(peerConnection, dataChannel, diagnostic);
    let jobId: string | undefined;
    let inputSent = false;
    const runStartedAt = Date.now();
    if (prepared) {
      registerPreparedJobConnectionDiagnostics(prepared, diagnostic);
    } else {
      registerConnectionDiagnostics(peerConnection, dataChannel, diagnostic);
    }

    try {
      emitDiagnostic(peerConnection, dataChannel, diagnostic, {
        stage: 'job-prewarm',
        message: prewarmHit ? 'job prewarm hit' : 'job prewarm miss',
        prewarmHit,
        elapsedMs: Date.now() - runStartedAt,
        stageStartedAt: runStartedAt,
      });
      if (attempt > 0) {
        emitDiagnostic(peerConnection, dataChannel, diagnostic, {
          stage: 'job-retry',
          message: `retry attempt=${attempt}`,
          prewarmHit,
          elapsedMs: Date.now() - runStartedAt,
          stageStartedAt: runStartedAt,
        });
      }
      status('creating offer');
      const offerGatherStartedAt = Date.now();
      const offer = await peerConnection.createOffer();
      await peerConnection.setLocalDescription(offer);
      await waitForIceGatheringComplete(peerConnection, timeoutMs);
      const offerGatheringMs = Date.now() - offerGatherStartedAt;
      if (!peerConnection.localDescription) {
        throw new Error('localDescription was not created');
      }
      emitDiagnostic(peerConnection, dataChannel, diagnostic, {
        stage: 'local-offer',
        message: 'created local job offer',
        elapsedMs: Date.now() - runStartedAt,
        stageStartedAt: offerGatherStartedAt,
        prewarmHit,
        offerGatheringMs,
        localCandidateSummary: summarizeSdpCandidates(peerConnection.localDescription.sdp),
        localSdp: peerConnection.localDescription.sdp,
      });

      status('creating job');
      const created = await this.request<JobCreateResult>('/v1/jobs', {
        method: 'POST',
        body: JSON.stringify({
          handler_type: handlerType,
          slave_app_id: slaveAppId,
          offer: {
            type: 'offer',
            sdp: peerConnection.localDescription.sdp,
          },
        }),
      });
      jobId = created.job.id;
      options.onJobCreated?.(created.job);

      status('waiting for answer');
      const answerWaitStartedAt = Date.now();
      const answer = await this.waitJobAnswer(created.job.id, timeoutMs);
      const answerWaitMs = Date.now() - answerWaitStartedAt;
      if (!answer.answer || answer.answer.type !== 'answer' || !answer.answer.sdp) {
        throw new Error(answer.last_error || `job ${created.job.id} did not produce an answer (state=${answer.state})`);
      }
      await peerConnection.setRemoteDescription({ type: 'answer', sdp: answer.answer.sdp });
      emitDiagnostic(peerConnection, dataChannel, diagnostic, {
        stage: 'remote-answer',
        message: 'received remote job answer',
        elapsedMs: Date.now() - runStartedAt,
        stageStartedAt: answerWaitStartedAt,
        prewarmHit,
        answerWaitMs,
        remoteCandidateSummary: summarizeSdpCandidates(answer.answer.sdp),
        remoteSdp: answer.answer.sdp,
      });

      status('waiting for data channel');
      const dataChannelOpenStartedAt = Date.now();
      await jobPeer.waitUntilOpen(timeoutMs);
      const dataChannelOpenMs = Date.now() - dataChannelOpenStartedAt;
      emitDiagnostic(peerConnection, dataChannel, diagnostic, {
        stage: 'data-channel-open',
        message: 'job data channel opened',
        elapsedMs: Date.now() - runStartedAt,
        stageStartedAt: dataChannelOpenStartedAt,
        prewarmHit,
        dataChannelOpenMs,
      });
      dataChannel.send(JSON.stringify({ kind: 'job.ready', id: created.job.id, input: input === undefined ? null : input }));
      inputSent = true;
      emitDiagnostic(peerConnection, dataChannel, diagnostic, {
        stage: 'job-ready',
        message: input === undefined ? 'sent job ready' : 'sent job input',
        elapsedMs: Date.now() - runStartedAt,
        prewarmHit,
      });
      status('waiting for result');
      return await jobPeer.waitForResult<TResult>(created.job.id, timeoutMs);
    } catch (error) {
      peerConnection.close();
      const detail = error instanceof Error ? error.message : String(error);
      throw new RunJobAttemptError(jobId ? `job ${jobId} failed: ${detail}` : detail, jobId, inputSent);
    }
  }

  private async killJobBestEffort(jobId?: string): Promise<void> {
    if (!jobId) {
      return;
    }
    try {
      await this.request<{ ok: boolean }>(`/v1/jobs/${encodeURIComponent(jobId)}/kill`, { method: 'POST' });
    } catch {
      // Best-effort cleanup only; the retry path should still surface its own result.
    }
  }

  private takePrewarmedJobConnection(slaveAppId: string, rtcConfig: RTCConfiguration): PreparedJobConnection | undefined {
    const key = jobConnectionKey(slaveAppId, rtcConfig);
    this.dropClosedPrewarmedJobConnections();
    const index = this.prewarmedJobConnections.findIndex((item) => item.key === key);
    if (index === -1) {
      return undefined;
    }
    return this.prewarmedJobConnections.splice(index, 1)[0];
  }

  private dropClosedPrewarmedJobConnections(): void {
    for (let index = this.prewarmedJobConnections.length - 1; index >= 0; index -= 1) {
      const item = this.prewarmedJobConnections[index];
      if (item.peerConnection.signalingState === 'closed' || item.dataChannel.readyState === 'closed') {
        this.prewarmedJobConnections.splice(index, 1);
      }
    }
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${this.apiBaseUrl}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.token}`,
        ...init.headers,
      },
    });
    if (!response.ok) {
      throw new Error(`${response.status} ${await response.text()}`);
    }
    return (await response.json()) as T;
  }

  private async waitJobAnswer(jobId: string, timeoutMs: number): Promise<JobAnswerWaitResult> {
    const startedAt = Date.now();
    while (true) {
      const elapsed = Date.now() - startedAt;
      if (elapsed > timeoutMs) {
        throw new Error(`job answer timeout: ${jobId}`);
      }
      const waitSeconds = Math.max(0, Math.min(30, Math.floor((timeoutMs - elapsed) / 1000)));
      const result = await this.request<JobAnswerWaitResult>(
        `/v1/jobs/${encodeURIComponent(jobId)}/wait-answer?wait_seconds=${waitSeconds}`,
      );
      if (result.answer || ['failed', 'cancelled', 'killed', 'succeeded'].includes(result.state)) {
        return result;
      }
    }
  }
}

function decodeBinaryFrame(frame: Uint8Array): { header: AttachmentChunkHeader; body: Uint8Array } {
  if (frame.byteLength < 4) {
    throw new Error('binary frame is too short');
  }
  const headerLength = new DataView(frame.buffer, frame.byteOffset, frame.byteLength).getUint32(0, false);
  if (headerLength <= 0 || frame.byteLength < 4 + headerLength) {
    throw new Error('invalid binary frame header length');
  }
  const header = JSON.parse(textDecoder.decode(frame.slice(4, 4 + headerLength))) as AttachmentChunkHeader;
  return { header, body: frame.slice(4 + headerLength) };
}

async function rawToUint8Array(rawData: unknown): Promise<Uint8Array> {
  if (rawData instanceof ArrayBuffer) {
    return new Uint8Array(rawData);
  }
  if (ArrayBuffer.isView(rawData)) {
    const view = rawData as ArrayBufferView;
    return new Uint8Array(view.buffer, view.byteOffset, view.byteLength);
  }
  if (typeof Blob !== 'undefined' && rawData instanceof Blob) {
    return new Uint8Array(await rawData.arrayBuffer());
  }
  throw new Error('unsupported binary message type');
}

function toArrayBuffer(data: Uint8Array): ArrayBuffer {
  const buffer = new ArrayBuffer(data.byteLength);
  new Uint8Array(buffer).set(data);
  return buffer;
}

function asError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}

class GpStationJobPeer {
  private response?: PendingResponse;
  private resolveResult?: (value: CallResult<unknown>) => void;
  private rejectResult?: (reason: Error) => void;
  private resultTimer?: ReturnType<typeof setTimeout>;
  private settled = false;
  private resultAcknowledged = false;

  constructor(
    private readonly peerConnection: RTCPeerConnection,
    private readonly dataChannel: RTCDataChannel,
    private readonly diagnostic: (event: ConnectDiagnosticEvent) => void,
  ) {
    this.dataChannel.binaryType = 'arraybuffer';
    this.dataChannel.addEventListener('message', (event) => {
      void this.handleDataMessage(event.data);
    });
    this.dataChannel.addEventListener('close', () => this.rejectPending(new Error('data channel closed')));
    this.dataChannel.addEventListener('error', () => this.rejectPending(new Error('data channel error')));
  }

  waitUntilOpen(timeoutMs: number): Promise<void> {
    if (this.dataChannel.readyState === 'open') {
      return Promise.resolve();
    }
    return new Promise((resolve, reject) => {
      const timer = setTimeout(
        () => reject(new Error(`data channel open timeout (${this.connectionStateSummary()})`)),
        timeoutMs,
      );
      this.dataChannel.addEventListener(
        'open',
        () => {
          clearTimeout(timer);
          resolve();
        },
        { once: true },
      );
    });
  }

  waitForResult<TResult>(jobId: string, timeoutMs: number): Promise<CallResult<TResult>> {
    return new Promise((resolve, reject) => {
      this.resultTimer = setTimeout(() => {
        this.rejectPending(new Error(`job result timeout: ${jobId}`));
      }, timeoutMs);
      this.resolveResult = resolve as (value: CallResult<unknown>) => void;
      this.rejectResult = reject;
    });
  }

  private async handleDataMessage(rawData: unknown): Promise<void> {
    try {
      if (typeof rawData === 'string') {
        await this.handleControlMessage(JSON.parse(rawData) as CallResponseFrame | CallErrorFrame | { kind: string; id: string; type?: string; payload?: unknown; attachments?: AttachmentMetadata[] });
        return;
      }
      await this.handleBinaryMessage(await rawToUint8Array(rawData));
    } catch (error) {
      this.rejectPending(asError(error));
    }
  }

  private async handleControlMessage(message: CallResponseFrame | CallErrorFrame | { kind: string; id: string; type?: string; payload?: unknown; attachments?: AttachmentMetadata[] }): Promise<void> {
    if (message.kind === 'call.error' || message.kind === 'job.error') {
      this.rejectPending(new Error((message as CallErrorFrame).detail || 'job error'));
      return;
    }
    if (message.kind !== 'job.result') {
      return;
    }
    emitDiagnostic(this.peerConnection, this.dataChannel, this.diagnostic, {
      stage: 'job-result',
      message: 'received job result',
    });
    const files = new Map<string, IncomingFile>();
    for (const attachment of message.attachments ?? []) {
      files.set(attachment.id, {
        ...attachment,
        chunks: [],
        receivedSize: 0,
        nextIndex: 0,
        complete: false,
      });
    }
    this.response = {
      id: message.id,
      payload: message.payload,
      attachments: message.attachments ?? [],
      files,
    };
    if (files.size === 0) {
      await this.resolvePending();
    }
  }

  private async handleBinaryMessage(frame: Uint8Array): Promise<void> {
    const { header, body } = decodeBinaryFrame(frame);
    if (header.kind !== 'attachment.chunk' || !this.response) {
      return;
    }
    const file = this.response.files.get(header.attachmentId);
    if (!file) {
      throw new Error(`unknown attachment chunk: ${header.attachmentId}`);
    }
    if (header.index !== file.nextIndex) {
      throw new Error(`out-of-order attachment chunk: ${header.attachmentId}`);
    }
    file.chunks.push(body);
    file.receivedSize += body.byteLength;
    file.nextIndex += 1;
    file.complete = header.final;
    if (file.complete && file.receivedSize !== file.size) {
      throw new Error(`attachment size mismatch: ${header.attachmentId}`);
    }
    if ([...this.response.files.values()].every((item) => item.complete)) {
      await this.resolvePending();
    }
  }

  private async resolvePending(): Promise<void> {
    if (this.settled || !this.response || !this.resolveResult) {
      return;
    }
    try {
      await this.acknowledgeResult();
    } catch (error) {
      this.rejectPending(asError(error));
      return;
    }
    this.settled = true;
    if (this.resultTimer) {
      clearTimeout(this.resultTimer);
    }
    const files = this.response.attachments.map((metadata) => {
      const file = this.response?.files.get(metadata.id);
      const chunks = file?.chunks ?? [];
      return {
        ...metadata,
        blob: new Blob(chunks.map(toArrayBuffer), { type: metadata.mimeType }),
      };
    });
    this.resolveResult({ payload: this.response.payload, files });
    this.cleanup();
  }

  private rejectPending(error: Error): void {
    if (this.settled) {
      return;
    }
    this.settled = true;
    if (this.resultTimer) {
      clearTimeout(this.resultTimer);
    }
    this.rejectResult?.(error);
    this.cleanup();
  }

  private cleanup(): void {
    this.resolveResult = undefined;
    this.rejectResult = undefined;
    this.resultTimer = undefined;
    this.peerConnection.close();
  }

  private async acknowledgeResult(): Promise<void> {
    if (this.resultAcknowledged) {
      return;
    }
    const jobId = this.response?.id;
    if (!jobId) {
      throw new Error('job result did not include an id');
    }
    if (this.dataChannel.readyState !== 'open') {
      throw new Error('data channel closed before job result ack');
    }
    this.dataChannel.send(JSON.stringify({ kind: 'job.result.ack', id: jobId }));
    await this.waitForAckBufferedAmountLow();
    this.resultAcknowledged = true;
    emitDiagnostic(this.peerConnection, this.dataChannel, this.diagnostic, {
      stage: 'job-result-ack',
      message: 'sent job result ack',
    });
  }

  private waitForAckBufferedAmountLow(): Promise<void> {
    if (this.dataChannel.readyState !== 'open') {
      return Promise.reject(new Error('data channel closed before job result ack'));
    }
    if (this.dataChannel.bufferedAmount === 0) {
      return Promise.resolve();
    }
    this.dataChannel.bufferedAmountLowThreshold = 0;
    return new Promise((resolve, reject) => {
      let timer: ReturnType<typeof setTimeout>;
      const cleanup = () => {
        clearTimeout(timer);
        this.dataChannel.removeEventListener('bufferedamountlow', onLow);
        this.dataChannel.removeEventListener('close', onClose);
        this.dataChannel.removeEventListener('error', onError);
      };
      const onLow = () => {
        cleanup();
        resolve();
      };
      const onClose = () => {
        cleanup();
        reject(new Error('data channel closed before job result ack'));
      };
      const onError = () => {
        cleanup();
        reject(new Error('data channel error before job result ack'));
      };
      this.dataChannel.addEventListener('bufferedamountlow', onLow);
      this.dataChannel.addEventListener('close', onClose);
      this.dataChannel.addEventListener('error', onError);
      timer = setTimeout(() => {
        cleanup();
        reject(new Error('job result ack buffered amount timeout'));
      }, 1000);
    });
  }

  private connectionStateSummary(): string {
    return [
      `signaling=${this.peerConnection.signalingState}`,
      `iceGathering=${this.peerConnection.iceGatheringState}`,
      `iceConnection=${this.peerConnection.iceConnectionState}`,
      `connection=${this.peerConnection.connectionState}`,
      `dataChannel=${this.dataChannel.readyState}`,
    ].join(', ');
  }
}

export function parseRtcIceServersJson(value: string): RTCIceServer[] {
  const parsed = JSON.parse(value) as unknown;
  if (!Array.isArray(parsed)) {
    throw new Error('RTC ICE servers JSON must be an array');
  }
  for (const item of parsed) {
    if (!isRtcIceServer(item)) {
      throw new Error('RTC ICE servers JSON must contain objects with urls');
    }
  }
  return parsed;
}

export function summarizeSdpCandidates(sdp: string): CandidateSummary {
  const summary: CandidateSummary = { host: 0, srflx: 0, relay: 0, prflx: 0, unknown: 0, total: 0 };
  for (const line of sdp.split(/\r?\n/)) {
    if (!line.startsWith('a=candidate:')) {
      continue;
    }
    summary.total += 1;
    const match = /\btyp\s+(\S+)/.exec(line);
    const type = match?.[1];
    if (type === 'host' || type === 'srflx' || type === 'relay' || type === 'prflx') {
      summary[type] += 1;
    } else {
      summary.unknown += 1;
    }
  }
  return summary;
}

function isRtcIceServer(value: unknown): value is RTCIceServer {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const urls = (value as { urls?: unknown }).urls;
  return typeof urls === 'string' || (Array.isArray(urls) && urls.every((item) => typeof item === 'string'));
}

function rtcConfigWithDefaults(config?: RTCConfiguration): RTCConfiguration {
  return {
    ...(config ?? {}),
    iceServers: config?.iceServers ?? DEFAULT_RTC_ICE_SERVERS,
    iceCandidatePoolSize: config?.iceCandidatePoolSize ?? DEFAULT_RTC_ICE_CANDIDATE_POOL_SIZE,
  };
}

function jobConnectionKey(slaveAppId: string, rtcConfig: RTCConfiguration): string {
  return `${slaveAppId}:${JSON.stringify(rtcConfig)}`;
}

function createPreparedJobConnection(slaveAppId: string, rtcConfig: RTCConfiguration): PreparedJobConnection {
  const peerConnection = new RTCPeerConnection(rtcConfig);
  const dataChannel = peerConnection.createDataChannel('gpstation.v1', { ordered: true });
  return {
    peerConnection,
    dataChannel,
    key: jobConnectionKey(slaveAppId, rtcConfig),
    slaveAppId,
    rtcConfig,
    diagnosticsRegistered: false,
  };
}

function registerPreparedJobConnectionDiagnostics(
  prepared: PreparedJobConnection,
  diagnostic: (event: ConnectDiagnosticEvent) => void,
): void {
  if (prepared.diagnosticsRegistered) {
    return;
  }
  registerConnectionDiagnostics(prepared.peerConnection, prepared.dataChannel, diagnostic);
  prepared.diagnosticsRegistered = true;
}

function registerConnectionDiagnostics(
  peerConnection: RTCPeerConnection,
  dataChannel: RTCDataChannel,
  diagnostic: (event: ConnectDiagnosticEvent) => void,
): void {
  peerConnection.addEventListener('signalingstatechange', () => {
    emitDiagnostic(peerConnection, dataChannel, diagnostic, {
      stage: 'signaling-state',
      message: `signaling state: ${peerConnection.signalingState}`,
    });
  });
  peerConnection.addEventListener('icegatheringstatechange', () => {
    emitDiagnostic(peerConnection, dataChannel, diagnostic, {
      stage: 'ice-gathering-state',
      message: `ICE gathering state: ${peerConnection.iceGatheringState}`,
    });
  });
  peerConnection.addEventListener('iceconnectionstatechange', () => {
    emitDiagnostic(peerConnection, dataChannel, diagnostic, {
      stage: 'ice-connection-state',
      message: `ICE connection state: ${peerConnection.iceConnectionState}`,
    });
  });
  peerConnection.addEventListener('connectionstatechange', () => {
    emitDiagnostic(peerConnection, dataChannel, diagnostic, {
      stage: 'connection-state',
      message: `peer connection state: ${peerConnection.connectionState}`,
    });
  });
  dataChannel.addEventListener('open', () => {
    emitDiagnostic(peerConnection, dataChannel, diagnostic, {
      stage: 'data-channel-state',
      message: 'data channel state: open',
    });
  });
  dataChannel.addEventListener('close', () => {
    emitDiagnostic(peerConnection, dataChannel, diagnostic, {
      stage: 'data-channel-state',
      message: 'data channel state: closed',
    });
  });
  dataChannel.addEventListener('error', () => {
    emitDiagnostic(peerConnection, dataChannel, diagnostic, {
      stage: 'data-channel-state',
      message: 'data channel state: error',
    });
  });
}

function emitDiagnostic(
  peerConnection: RTCPeerConnection,
  dataChannel: RTCDataChannel,
  diagnostic: (event: ConnectDiagnosticEvent) => void,
  event: ConnectDiagnosticEvent,
): void {
  diagnostic({
    signalingState: peerConnection.signalingState,
    iceGatheringState: peerConnection.iceGatheringState,
    iceConnectionState: peerConnection.iceConnectionState,
    connectionState: peerConnection.connectionState,
    dataChannelState: dataChannel.readyState,
    ...event,
  });
}

function waitForIceGatheringComplete(
  peerConnection: RTCPeerConnection,
  timeoutMs: number,
): Promise<void> {
  if (peerConnection.iceGatheringState === 'complete') {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, timeoutMs);
    peerConnection.addEventListener('icegatheringstatechange', () => {
      if (peerConnection.iceGatheringState === 'complete') {
        clearTimeout(timer);
        resolve();
      }
    });
  });
}
