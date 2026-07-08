import { emitDiagnostic, registerConnectionDiagnostics, registerPreparedJobConnectionDiagnostics } from './diagnostics.js';
import { GpStationJobPeer } from './job-peer.js';
import {
  createPreparedJobConnection,
  jobConnectionKey,
  rtcConfigWithDefaults,
  summarizeSdpCandidates,
  waitForIceGatheringComplete,
} from './rtc.js';
import type {
  CallResult,
  ConnectDiagnosticEvent,
  GpStationClientOptions,
  JobAnswerWaitResult,
  JobConnectionPrewarmOptions,
  JobCreateResult,
  LauncherView,
  PreparedJobConnection,
  RunJobOptions,
} from './types.js';

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
