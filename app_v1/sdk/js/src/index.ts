export type WorkerSessionView = {
  id: string;
  user_id: string;
  worker_name: string;
  status: string;
  capabilities: string[];
  active_session_count: number;
  connected_at: string;
  last_heartbeat_at: string;
};

export type SessionDescriptor = {
  session_id: string;
  worker_session_id: string;
  signaling_url: string;
  token: string;
  expires_at: string;
};

export type SignalPayload =
  | { type: 'offer'; sdp: string }
  | { type: 'answer'; sdp: string }
  | { type: 'ice'; candidate?: string; sdpMid?: string; sdpMLineIndex?: number }
  | { type: 'end-of-candidates' };

export type DataChannelEnvelope<T = unknown> = {
  id: string;
  type: 'echo.request' | 'echo.result' | 'error';
  payload?: T;
};

export type GpStationClientOptions = {
  apiBaseUrl: string;
  token: string;
  rtcConfig?: RTCConfiguration;
};

export type CreateSessionOptions = {
  workerSessionId: string;
  ttlSeconds?: number;
};

export type ConnectOptions = {
  timeoutMs?: number;
  onStatus?: (status: string) => void;
};

type PendingEcho = {
  resolve: (value: unknown) => void;
  reject: (reason: Error) => void;
  timer: ReturnType<typeof setTimeout>;
};

export class GpStationClient {
  private readonly apiBaseUrl: string;
  private readonly token: string;
  private readonly rtcConfig?: RTCConfiguration;

  constructor(options: GpStationClientOptions) {
    this.apiBaseUrl = options.apiBaseUrl.replace(/\/+$/, '') || 'http://127.0.0.1:8100';
    this.token = options.token;
    this.rtcConfig = options.rtcConfig;
  }

  async listWorkers(): Promise<WorkerSessionView[]> {
    return this.request<WorkerSessionView[]>('/v1/workers');
  }

  async createSession(options: CreateSessionOptions): Promise<SessionDescriptor> {
    return this.request<SessionDescriptor>('/v1/sessions', {
      method: 'POST',
      body: JSON.stringify({
        worker_session_id: options.workerSessionId,
        ttl_seconds: options.ttlSeconds,
      }),
    });
  }

  async connectSession(
    descriptor: SessionDescriptor,
    options: ConnectOptions = {},
  ): Promise<GpStationPeer> {
    const status = options.onStatus ?? (() => undefined);
    const timeoutMs = options.timeoutMs ?? 15000;
    const peerConnection = new RTCPeerConnection(this.rtcConfig);
    const dataChannel = peerConnection.createDataChannel('gpstation.v1', { ordered: true });
    const socket = new WebSocket(descriptor.signaling_url);
    const peer = new GpStationPeer(peerConnection, dataChannel, socket);

    status('opening signaling socket');
    await waitForSocketOpen(socket, timeoutMs);
    socket.addEventListener('message', (event) => {
      void handleSignalMessage(peerConnection, event.data, status);
    });

    status('creating offer');
    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);
    await waitForIceGatheringComplete(peerConnection, timeoutMs);

    if (!peerConnection.localDescription) {
      throw new Error('localDescription was not created');
    }

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
    status('connected');
    return peer;
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
}

export class GpStationPeer {
  private readonly pending = new Map<string, PendingEcho>();

  constructor(
    private readonly peerConnection: RTCPeerConnection,
    private readonly dataChannel: RTCDataChannel,
    private readonly socket: WebSocket,
  ) {
    this.dataChannel.addEventListener('message', (event) => this.handleDataMessage(event.data));
    this.dataChannel.addEventListener('close', () => this.rejectAll(new Error('data channel closed')));
  }

  waitUntilOpen(timeoutMs: number): Promise<void> {
    if (this.dataChannel.readyState === 'open') {
      return Promise.resolve();
    }
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('data channel open timeout')), timeoutMs);
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

  echo<T>(payload: T, timeoutMs = 10000): Promise<T> {
    if (this.dataChannel.readyState !== 'open') {
      return Promise.reject(new Error('data channel is not open'));
    }
    const id = crypto.randomUUID();
    const envelope: DataChannelEnvelope<T> = { id, type: 'echo.request', payload };
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error('echo timeout'));
      }, timeoutMs);
      this.pending.set(id, { resolve: resolve as (value: unknown) => void, reject, timer });
      this.dataChannel.send(JSON.stringify(envelope));
    });
  }

  close(): void {
    this.rejectAll(new Error('connection closed'));
    this.dataChannel.close();
    this.peerConnection.close();
    this.socket.close();
  }

  private handleDataMessage(rawData: unknown): void {
    const text = typeof rawData === 'string' ? rawData : new TextDecoder().decode(rawData as ArrayBuffer);
    const message = JSON.parse(text) as DataChannelEnvelope;
    if (message.type === 'error') {
      this.rejectAll(new Error(String((message.payload as { detail?: string })?.detail ?? 'worker error')));
      return;
    }
    const pending = this.pending.get(message.id);
    if (!pending) {
      return;
    }
    clearTimeout(pending.timer);
    this.pending.delete(message.id);
    pending.resolve(message.payload);
  }

  private rejectAll(error: Error): void {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
  }
}

async function handleSignalMessage(
  peerConnection: RTCPeerConnection,
  rawData: string,
  status: (status: string) => void,
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
    return;
  }
  if (payload.signal.type === 'ice') {
    await peerConnection.addIceCandidate(payload.signal.candidate ? payload.signal : null);
  }
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
