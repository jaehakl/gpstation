import { asError, decodeBinaryFrame, rawToUint8Array, toArrayBuffer } from './binary.js';
import { emitDiagnostic } from './diagnostics.js';
import type {
  AttachmentMetadata,
  CallResult,
  ConnectDiagnosticEvent,
  IncomingFile,
  PendingResponse,
} from './types.js';

type JobControlFrame = {
  kind: string;
  id?: string;
  type?: string;
  payload?: unknown;
  attachments?: AttachmentMetadata[];
  detail?: string;
};

export class GpStationJobPeer {
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
        await this.handleControlMessage(JSON.parse(rawData) as JobControlFrame);
        return;
      }
      await this.handleBinaryMessage(await rawToUint8Array(rawData));
    } catch (error) {
      this.rejectPending(asError(error));
    }
  }

  private async handleControlMessage(message: JobControlFrame): Promise<void> {
    if (message.kind === 'job.error') {
      this.rejectPending(new Error(message.detail || 'job error'));
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
