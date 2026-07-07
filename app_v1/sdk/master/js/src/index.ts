export type LauncherSessionView = {
  id: string;
  user_id: string;
  launcher_name: string;
  status: string;
  slave_app_ids: string[];
  active_session_count: number;
  connected_at: string;
  last_heartbeat_at: string;
};

export type SessionDescriptor = {
  session_id: string;
  launcher_session_id: string;
  slave_app_id: string;
  signaling_url: string;
  token: string;
  expires_at: string;
};

export type JobDescriptor = {
  id: string;
  user_id: string;
  handler_type: string;
  slave_app_id: string;
  input?: unknown;
  offer: SignalPayload;
  answer?: SignalPayload | null;
  result?: unknown;
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
  result?: unknown;
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

export type CallRequestFrame<T = unknown> = {
  kind: 'call.request';
  id: string;
  type: string;
  payload?: T;
  attachments: AttachmentMetadata[];
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

export type CallFileObject = {
  name?: string;
  mimeType?: string;
  data: Blob | ArrayBuffer | Uint8Array;
};

export type CallFileInput = File | Blob | CallFileObject;

export type CallOptions = {
  files?: CallFileInput[];
  timeoutMs?: number;
  chunkSize?: number;
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

export type CreateSessionOptions = {
  launcherSessionId: string;
  slaveAppId?: string;
  ttlSeconds?: number;
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

type NormalizedFile = AttachmentMetadata & {
  data: Uint8Array;
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

type PendingCall = {
  resolve: (value: CallResult<unknown>) => void;
  reject: (reason: Error) => void;
  timer: ReturnType<typeof setTimeout>;
  response?: PendingResponse;
};

const DEFAULT_CHUNK_SIZE = 16 * 1024;
const BUFFERED_AMOUNT_HIGH_WATER_MARK = 512 * 1024;
const BUFFERED_AMOUNT_LOW_WATER_MARK = 128 * 1024;
export const DEFAULT_RTC_ICE_SERVERS: RTCIceServer[] = [{ urls: 'stun:stun.l.google.com:19302' }];
const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();

export class GpStationClient {
  private readonly apiBaseUrl: string;
  private readonly token: string;
  private readonly rtcConfig?: RTCConfiguration;

  constructor(options: GpStationClientOptions) {
    this.apiBaseUrl = options.apiBaseUrl.replace(/\/+$/, '');
    this.token = options.token;
    this.rtcConfig = options.rtcConfig;
  }

  async listLaunchers(): Promise<LauncherSessionView[]> {
    return this.request<LauncherSessionView[]>('/v1/launchers');
  }

  async createSession(options: CreateSessionOptions): Promise<SessionDescriptor> {
    return this.request<SessionDescriptor>('/v1/sessions', {
      method: 'POST',
      body: JSON.stringify({
        launcher_session_id: options.launcherSessionId,
        slave_app_id: options.slaveAppId ?? 'echo',
        ttl_seconds: options.ttlSeconds,
      }),
    });
  }

  async connectSession(
    descriptor: SessionDescriptor,
    options: ConnectOptions = {},
  ): Promise<GpStationPeer> {
    const status = options.onStatus ?? (() => undefined);
    const diagnostic = options.onDiagnostic ?? (() => undefined);
    const timeoutMs = options.timeoutMs ?? 15000;
    const peerConnection = new RTCPeerConnection(this.rtcConfig ?? { iceServers: DEFAULT_RTC_ICE_SERVERS });
    const dataChannel = peerConnection.createDataChannel('gpstation.v1', { ordered: true });
    const socket = new WebSocket(descriptor.signaling_url);
    const peer = new GpStationPeer(peerConnection, dataChannel, socket);
    registerConnectionDiagnostics(peerConnection, dataChannel, diagnostic);
    emitDiagnostic(peerConnection, dataChannel, diagnostic, {
      stage: 'peer-created',
      message: 'created RTCPeerConnection',
    });

    status('opening signaling socket');
    await waitForSocketOpen(socket, timeoutMs);
    socket.addEventListener('message', (event) => {
      void handleSignalMessage(peerConnection, dataChannel, event.data, status, diagnostic);
    });

    status('creating offer');
    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);
    await waitForIceGatheringComplete(peerConnection, timeoutMs);

    if (!peerConnection.localDescription) {
      throw new Error('localDescription was not created');
    }
    emitDiagnostic(peerConnection, dataChannel, diagnostic, {
      stage: 'local-offer',
      message: 'created local offer',
      localCandidateSummary: summarizeSdpCandidates(peerConnection.localDescription.sdp),
      localSdp: peerConnection.localDescription.sdp,
    });

    socket.send(
      JSON.stringify({
        signal: {
          type: 'offer',
          sdp: peerConnection.localDescription.sdp,
        },
      }),
    );

    status('waiting for data channel');
    await peer.waitUntilOpen(timeoutMs);
    emitDiagnostic(peerConnection, dataChannel, diagnostic, {
      stage: 'connected',
      message: 'data channel opened',
    });
    status('connected');
    return peer;
  }

  async runJob<TInput = unknown, TResult = unknown>(
    handlerType: string,
    input?: TInput,
    options: RunJobOptions = {},
  ): Promise<CallResult<TResult>> {
    const status = options.onStatus ?? (() => undefined);
    const diagnostic = options.onDiagnostic ?? (() => undefined);
    const timeoutMs = options.timeoutMs ?? 60000;
    const peerConnection = new RTCPeerConnection(options.rtcConfig ?? this.rtcConfig ?? { iceServers: DEFAULT_RTC_ICE_SERVERS });
    const dataChannel = peerConnection.createDataChannel('gpstation.v1', { ordered: true });
    const jobPeer = new GpStationJobPeer(peerConnection, dataChannel, diagnostic);
    let jobId: string | undefined;
    registerConnectionDiagnostics(peerConnection, dataChannel, diagnostic);

    try {
      status('creating offer');
      const offer = await peerConnection.createOffer();
      await peerConnection.setLocalDescription(offer);
      await waitForIceGatheringComplete(peerConnection, timeoutMs);
      if (!peerConnection.localDescription) {
        throw new Error('localDescription was not created');
      }
      emitDiagnostic(peerConnection, dataChannel, diagnostic, {
        stage: 'local-offer',
        message: 'created local job offer',
        localCandidateSummary: summarizeSdpCandidates(peerConnection.localDescription.sdp),
        localSdp: peerConnection.localDescription.sdp,
      });

      status('creating job');
      const created = await this.request<JobCreateResult>('/v1/jobs', {
        method: 'POST',
        body: JSON.stringify({
          handler_type: handlerType,
          slave_app_id: options.slaveAppId ?? 'echo',
          input,
          offer: {
            type: 'offer',
            sdp: peerConnection.localDescription.sdp,
          },
        }),
      });
      jobId = created.job.id;
      options.onJobCreated?.(created.job);

      status('waiting for answer');
      const answer = await this.waitJobAnswer(created.job.id, timeoutMs);
      if (!answer.answer || answer.answer.type !== 'answer' || !answer.answer.sdp) {
        throw new Error(answer.last_error || `job ${created.job.id} did not produce an answer (state=${answer.state})`);
      }
      await peerConnection.setRemoteDescription({ type: 'answer', sdp: answer.answer.sdp });
      emitDiagnostic(peerConnection, dataChannel, diagnostic, {
        stage: 'remote-answer',
        message: 'received remote job answer',
        remoteCandidateSummary: summarizeSdpCandidates(answer.answer.sdp),
        remoteSdp: answer.answer.sdp,
      });

      status('waiting for data channel');
      await jobPeer.waitUntilOpen(timeoutMs);
      dataChannel.send(JSON.stringify({ kind: 'job.ready', id: created.job.id }));
      status('waiting for result');
      return await jobPeer.waitForResult<TResult>(created.job.id, timeoutMs);
    } catch (error) {
      peerConnection.close();
      const detail = error instanceof Error ? error.message : String(error);
      throw new Error(jobId ? `job ${jobId} failed: ${detail}` : detail);
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

export class GpStationPeer {
  private readonly pending = new Map<string, PendingCall>();

  constructor(
    private readonly peerConnection: RTCPeerConnection,
    private readonly dataChannel: RTCDataChannel,
    private readonly socket: WebSocket,
  ) {
    this.dataChannel.binaryType = 'arraybuffer';
    this.dataChannel.bufferedAmountLowThreshold = BUFFERED_AMOUNT_LOW_WATER_MARK;
    this.dataChannel.addEventListener('message', (event) => {
      void this.handleDataMessage(event.data);
    });
    this.dataChannel.addEventListener('close', () => this.rejectAll(new Error('data channel closed')));
    this.dataChannel.addEventListener('error', () => this.rejectAll(new Error('data channel error')));
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

  private connectionStateSummary(): string {
    return [
      `signaling=${this.peerConnection.signalingState}`,
      `iceGathering=${this.peerConnection.iceGatheringState}`,
      `iceConnection=${this.peerConnection.iceConnectionState}`,
      `connection=${this.peerConnection.connectionState}`,
      `dataChannel=${this.dataChannel.readyState}`,
    ].join(', ');
  }

  async call<TPayload = unknown, TResult = unknown>(
    handlerType: string,
    payload?: TPayload,
    options: CallOptions = {},
  ): Promise<CallResult<TResult>> {
    if (this.dataChannel.readyState !== 'open') {
      return Promise.reject(new Error('data channel is not open'));
    }
    const id = crypto.randomUUID();
    const timeoutMs = options.timeoutMs ?? 10000;
    const chunkSize = options.chunkSize ?? DEFAULT_CHUNK_SIZE;
    const files = await normalizeFiles(options.files ?? []);
    const frame: CallRequestFrame<TPayload> = {
      kind: 'call.request',
      id,
      type: handlerType,
      payload,
      attachments: files.map(fileMetadata),
    };

    const promise = new Promise<CallResult<TResult>>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`${handlerType} timeout`));
      }, timeoutMs);
      this.pending.set(id, {
        resolve: resolve as (value: CallResult<unknown>) => void,
        reject,
        timer,
      });
    });

    try {
      this.dataChannel.send(JSON.stringify(frame));
      void this.sendFiles(id, files, chunkSize).catch((error) => this.rejectPending(id, asError(error)));
    } catch (error) {
      this.rejectPending(id, asError(error));
    }
    return promise;
  }

  close(): void {
    this.rejectAll(new Error('connection closed'));
    this.dataChannel.close();
    this.peerConnection.close();
    this.socket.close();
  }

  private async sendFiles(callId: string, files: NormalizedFile[], chunkSize: number): Promise<void> {
    for (const file of files) {
      await this.sendFileChunks(callId, file, chunkSize);
    }
  }

  private async sendFileChunks(callId: string, file: NormalizedFile, chunkSize: number): Promise<void> {
    if (file.data.byteLength === 0) {
      this.dataChannel.send(
        encodeBinaryFrame(
          {
            kind: 'attachment.chunk',
            callId,
            attachmentId: file.id,
            index: 0,
            final: true,
          },
          new Uint8Array(),
        ),
      );
      await this.waitForBufferedAmountLow();
      return;
    }

    let index = 0;
    for (let offset = 0; offset < file.data.byteLength; offset += chunkSize) {
      const chunk = file.data.slice(offset, offset + chunkSize);
      this.dataChannel.send(
        encodeBinaryFrame(
          {
            kind: 'attachment.chunk',
            callId,
            attachmentId: file.id,
            index,
            final: offset + chunkSize >= file.data.byteLength,
          },
          chunk,
        ),
      );
      index += 1;
      await this.waitForBufferedAmountLow();
    }
  }

  private waitForBufferedAmountLow(): Promise<void> {
    if (this.dataChannel.readyState !== 'open') {
      return Promise.reject(new Error('data channel is not open'));
    }
    this.dataChannel.bufferedAmountLowThreshold = BUFFERED_AMOUNT_LOW_WATER_MARK;
    if (this.dataChannel.bufferedAmount <= BUFFERED_AMOUNT_HIGH_WATER_MARK) {
      return Promise.resolve();
    }
    return new Promise((resolve, reject) => {
      const cleanup = () => {
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
        reject(new Error('data channel closed while sending attachment'));
      };
      const onError = () => {
        cleanup();
        reject(new Error('data channel error while sending attachment'));
      };
      this.dataChannel.addEventListener('bufferedamountlow', onLow);
      this.dataChannel.addEventListener('close', onClose);
      this.dataChannel.addEventListener('error', onError);
    });
  }

  private async handleDataMessage(rawData: unknown): Promise<void> {
    try {
      if (typeof rawData === 'string') {
        this.handleControlMessage(JSON.parse(rawData) as CallResponseFrame | CallErrorFrame);
        return;
      }
      this.handleBinaryMessage(await rawToUint8Array(rawData));
    } catch (error) {
      this.rejectAll(asError(error));
    }
  }

  private handleControlMessage(message: CallResponseFrame | CallErrorFrame): void {
    if (message.kind === 'call.error') {
      const entry = this.findPendingErrorTarget(message.id);
      if (!entry) {
        return;
      }
      const [callId, pending] = entry;
      clearTimeout(pending.timer);
      this.pending.delete(callId);
      pending.reject(new Error(message.detail || message.code || 'launcher error'));
      return;
    }

    if (message.kind !== 'call.response') {
      throw new Error(`unsupported data channel message: ${(message as { kind?: string }).kind ?? 'missing kind'}`);
    }
    const pending = this.pending.get(message.id);
    if (!pending) {
      return;
    }
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
    pending.response = {
      payload: message.payload,
      attachments: message.attachments ?? [],
      files,
    };
    if (files.size === 0) {
      this.resolvePending(message.id);
    }
  }

  private handleBinaryMessage(frame: Uint8Array): void {
    const { header, body } = decodeBinaryFrame(frame);
    if (header.kind !== 'attachment.chunk') {
      throw new Error(`unsupported binary frame: ${String(header.kind)}`);
    }
    const pending = this.pending.get(header.callId);
    if (!pending?.response) {
      throw new Error(`unknown call for attachment chunk: ${header.callId}`);
    }
    const file = pending.response.files.get(header.attachmentId);
    if (!file) {
      throw new Error(`unknown attachment chunk: ${header.attachmentId}`);
    }
    if (header.index !== file.nextIndex) {
      throw new Error(`out-of-order attachment chunk: ${header.attachmentId}`);
    }
    if (file.complete) {
      throw new Error(`attachment chunk after final: ${header.attachmentId}`);
    }

    file.chunks.push(body);
    file.receivedSize += body.byteLength;
    file.nextIndex += 1;
    file.complete = header.final;
    if (file.receivedSize > file.size) {
      throw new Error(`attachment exceeded declared size: ${header.attachmentId}`);
    }
    if (file.complete && file.receivedSize !== file.size) {
      throw new Error(`attachment size mismatch: ${header.attachmentId}`);
    }
    if ([...pending.response.files.values()].every((item) => item.complete)) {
      this.resolvePending(header.callId);
    }
  }

  private resolvePending(callId: string): void {
    const pending = this.pending.get(callId);
    if (!pending?.response) {
      return;
    }
    clearTimeout(pending.timer);
    this.pending.delete(callId);
    const files = pending.response.attachments.map((metadata) => {
      const file = pending.response?.files.get(metadata.id);
      const chunks = file?.chunks ?? [];
      return {
        ...metadata,
        blob: new Blob(chunks.map(toArrayBuffer), { type: metadata.mimeType }),
      };
    });
    pending.resolve({
      payload: pending.response.payload,
      files,
    });
  }

  private rejectAll(error: Error): void {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
  }

  private rejectPending(callId: string, error: Error): void {
    const pending = this.pending.get(callId);
    if (!pending) {
      return;
    }
    clearTimeout(pending.timer);
    this.pending.delete(callId);
    pending.reject(error);
  }

  private findPendingErrorTarget(errorId: string): [string, PendingCall] | undefined {
    const pending = this.pending.get(errorId);
    if (pending) {
      return [errorId, pending];
    }
    if (this.pending.size !== 1) {
      return undefined;
    }
    return this.pending.entries().next().value;
  }
}

async function normalizeFiles(inputs: CallFileInput[]): Promise<NormalizedFile[]> {
  const files: NormalizedFile[] = [];
  for (const input of inputs) {
    files.push(await normalizeFile(input));
  }
  return files;
}

async function normalizeFile(input: CallFileInput): Promise<NormalizedFile> {
  if (typeof File !== 'undefined' && input instanceof File) {
    const data = new Uint8Array(await input.arrayBuffer());
    return {
      id: crypto.randomUUID(),
      name: input.name,
      mimeType: input.type || undefined,
      size: data.byteLength,
      data,
    };
  }
  if (typeof Blob !== 'undefined' && input instanceof Blob) {
    const data = new Uint8Array(await input.arrayBuffer());
    return {
      id: crypto.randomUUID(),
      mimeType: input.type || undefined,
      size: data.byteLength,
      data,
    };
  }
  const objectInput = input as CallFileObject;
  const data =
    objectInput.data instanceof Blob
      ? new Uint8Array(await objectInput.data.arrayBuffer())
      : toUint8Array(objectInput.data);
  return {
    id: crypto.randomUUID(),
    name: objectInput.name,
    mimeType: objectInput.mimeType,
    size: data.byteLength,
    data,
  };
}

function fileMetadata(file: NormalizedFile): AttachmentMetadata {
  const metadata: AttachmentMetadata = { id: file.id, size: file.size };
  if (file.name) {
    metadata.name = file.name;
  }
  if (file.mimeType) {
    metadata.mimeType = file.mimeType;
  }
  return metadata;
}

function encodeBinaryFrame(header: AttachmentChunkHeader, body: Uint8Array): ArrayBuffer {
  const headerBytes = textEncoder.encode(JSON.stringify(header));
  const frame = new Uint8Array(4 + headerBytes.byteLength + body.byteLength);
  new DataView(frame.buffer).setUint32(0, headerBytes.byteLength, false);
  frame.set(headerBytes, 4);
  frame.set(body, 4 + headerBytes.byteLength);
  return frame.buffer;
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

function toUint8Array(data: ArrayBuffer | Uint8Array): Uint8Array {
  return data instanceof Uint8Array ? new Uint8Array(toArrayBuffer(data)) : new Uint8Array(data);
}

function toArrayBuffer(data: Uint8Array): ArrayBuffer {
  const buffer = new ArrayBuffer(data.byteLength);
  new Uint8Array(buffer).set(data);
  return buffer;
}

function asError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}

async function handleSignalMessage(
  peerConnection: RTCPeerConnection,
  dataChannel: RTCDataChannel,
  rawData: string,
  status: (status: string) => void,
  diagnostic: (event: ConnectDiagnosticEvent) => void,
): Promise<void> {
  const payload = JSON.parse(rawData) as { signal?: SignalPayload; type?: string; detail?: string };
  if (payload.type === 'session.error') {
    throw new Error(payload.detail || 'session error');
  }
  if (!payload.signal) {
    return;
  }
  if (payload.signal.type === 'answer') {
    status('received answer');
    await peerConnection.setRemoteDescription({ type: 'answer', sdp: payload.signal.sdp });
    emitDiagnostic(peerConnection, dataChannel, diagnostic, {
      stage: 'remote-answer',
      message: 'received remote answer',
      remoteCandidateSummary: summarizeSdpCandidates(payload.signal.sdp),
      remoteSdp: payload.signal.sdp,
    });
    return;
  }
  if (payload.signal.type === 'ice') {
    await peerConnection.addIceCandidate(payload.signal.candidate ? payload.signal : null);
    emitDiagnostic(peerConnection, dataChannel, diagnostic, {
      stage: 'remote-ice',
      message: payload.signal.candidate ? 'received remote ICE candidate' : 'received end-of-candidates',
    });
  }
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

function waitForSocketOpen(socket: WebSocket, timeoutMs: number): Promise<void> {
  if (socket.readyState === WebSocket.OPEN) {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('signaling socket open timeout')), timeoutMs);
    socket.addEventListener(
      'open',
      () => {
        clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
    socket.addEventListener(
      'error',
      () => {
        clearTimeout(timer);
        reject(new Error('signaling socket failed'));
      },
      { once: true },
    );
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
