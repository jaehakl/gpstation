'use client';

import { PlugZap, RefreshCw, Send, Square, Wifi } from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import {
  GpStationClient,
  GpStationPeer,
  ReceivedFile,
  SessionDescriptor,
  WorkerSessionView,
} from '@gpstation/v1-master-js-sdk';

const defaultApiBaseUrl = process.env.NEXT_PUBLIC_GPSTATION_V1_API_URL || 'http://127.0.0.1:8100';

type LogItem = {
  id: number;
  message: string;
};

type DisplayFile = ReceivedFile & {
  url: string;
  isImage: boolean;
};

export default function Home() {
  const [apiBaseUrl, setApiBaseUrl] = useState(defaultApiBaseUrl);
  const [token, setToken] = useState('demo-client-token');
  const [workers, setWorkers] = useState<WorkerSessionView[]>([]);
  const [selectedWorkerId, setSelectedWorkerId] = useState('');
  const [selectedSlaveAppId, setSelectedSlaveAppId] = useState('echo');
  const [session, setSession] = useState<SessionDescriptor | null>(null);
  const [status, setStatus] = useState('idle');
  const [handlerType, setHandlerType] = useState('echo.request');
  const [requestJson, setRequestJson] = useState('{\n  "text": "hello gp station"\n}');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [resultJson, setResultJson] = useState('');
  const [resultFiles, setResultFiles] = useState<DisplayFile[]>([]);
  const [logs, setLogs] = useState<LogItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [connected, setConnected] = useState(false);
  const peerRef = useRef<GpStationPeer | null>(null);
  const logIdRef = useRef(0);

  const client = useMemo(
    () =>
      new GpStationClient({
        apiBaseUrl,
        token,
      }),
    [apiBaseUrl, token],
  );
  const selectedWorker = workers.find((worker) => worker.id === selectedWorkerId);
  const availableSlaveAppIds = selectedWorker?.slave_app_ids ?? [];

  function addLog(message: string) {
    const id = logIdRef.current + 1;
    logIdRef.current = id;
    setLogs((items) => [{ id, message }, ...items].slice(0, 12));
  }

  function clearResultFiles() {
    for (const file of resultFiles) {
      URL.revokeObjectURL(file.url);
    }
    setResultFiles([]);
  }

  async function refreshWorkers() {
    setBusy(true);
    try {
      const nextWorkers = await client.listWorkers();
      setWorkers(nextWorkers);
      const nextSelectedWorker = nextWorkers.find((worker) => worker.id === selectedWorkerId) ?? nextWorkers[0];
      if (nextSelectedWorker) {
        setSelectedWorkerId(nextSelectedWorker.id);
        setSelectedSlaveAppId(pickSlaveAppId(nextSelectedWorker, selectedSlaveAppId));
      }
      setStatus('workers refreshed');
      addLog(`workers: ${nextWorkers.length}`);
    } catch (error) {
      setStatus('worker refresh failed');
      addLog(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function connect() {
    if (!selectedWorkerId) {
      setStatus('select worker');
      return;
    }
    if (!selectedSlaveAppId) {
      setStatus('select slave app');
      return;
    }
    setBusy(true);
    setResultJson('');
    clearResultFiles();
    peerRef.current?.close();
    peerRef.current = null;
    setConnected(false);
    try {
      const descriptor = await client.createSession({
        workerSessionId: selectedWorkerId,
        slaveAppId: selectedSlaveAppId,
      });
      setSession(descriptor);
      addLog(`session: ${descriptor.session_id}`);
      const peer = await client.connectSession(descriptor, {
        onStatus: (nextStatus) => {
          setStatus(nextStatus);
          addLog(nextStatus);
        },
      });
      peerRef.current = peer;
      setConnected(true);
      setStatus('connected');
    } catch (error) {
      setStatus('connection failed');
      addLog(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function sendCall() {
    const peer = peerRef.current;
    if (!peer) {
      setStatus('not connected');
      return;
    }
    let payload: unknown;
    try {
      payload = requestJson.trim() ? JSON.parse(requestJson) : null;
    } catch (error) {
      setStatus('invalid JSON');
      addLog(error instanceof Error ? error.message : String(error));
      return;
    }

    setBusy(true);
    clearResultFiles();
    try {
      const result = await peer.call<unknown, unknown>(handlerType.trim(), payload, { files: selectedFiles });
      setResultJson(JSON.stringify(result.payload, null, 2));
      setResultFiles(
        result.files.map((file) => ({
          ...file,
          url: URL.createObjectURL(file.blob),
          isImage: Boolean(file.mimeType?.startsWith('image/')),
        })),
      );
      addLog(`${handlerType} result`);
      setStatus('call complete');
    } catch (error) {
      setStatus('call failed');
      addLog(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  function disconnect() {
    peerRef.current?.close();
    peerRef.current = null;
    setConnected(false);
    setStatus('disconnected');
    addLog('connection closed');
  }

  function selectWorker(worker: WorkerSessionView) {
    setSelectedWorkerId(worker.id);
    setSelectedSlaveAppId(pickSlaveAppId(worker, selectedSlaveAppId));
  }

  return (
    <main className="shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">GP Station v1</p>
          <h1>Worker DataChannel Console</h1>
        </div>
        <div className="statusPill">
          <Wifi size={16} aria-hidden="true" />
          <span>{status}</span>
        </div>
      </section>

      <section className="workspace">
        <div className="panel controlsPanel">
          <label>
            <span>Server</span>
            <input value={apiBaseUrl} onChange={(event) => setApiBaseUrl(event.target.value)} />
          </label>
          <label>
            <span>Token</span>
            <input value={token} onChange={(event) => setToken(event.target.value)} />
          </label>
          <div className="buttonRow">
            <button type="button" onClick={refreshWorkers} disabled={busy} title="Refresh workers">
              <RefreshCw size={17} aria-hidden="true" />
              <span>Refresh</span>
            </button>
            <button type="button" onClick={connect} disabled={busy || !selectedWorkerId || !selectedSlaveAppId} title="Connect">
              <PlugZap size={17} aria-hidden="true" />
              <span>Connect</span>
            </button>
            <button type="button" onClick={disconnect} title="Disconnect">
              <Square size={17} aria-hidden="true" />
              <span>Close</span>
            </button>
          </div>
          <label>
            <span>Worker</span>
            <select
              value={selectedWorkerId}
              onChange={(event) => {
                const worker = workers.find((item) => item.id === event.target.value);
                if (worker) {
                  selectWorker(worker);
                } else {
                  setSelectedWorkerId('');
                  setSelectedSlaveAppId('');
                }
              }}
            >
              <option value="">No worker selected</option>
              {workers.map((worker) => (
                <option key={worker.id} value={worker.id}>
                  {worker.worker_name} | {worker.status} | {worker.id.slice(0, 8)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Slave app</span>
            <select value={selectedSlaveAppId} onChange={(event) => setSelectedSlaveAppId(event.target.value)}>
              {availableSlaveAppIds.map((slaveAppId) => (
                <option key={slaveAppId} value={slaveAppId}>
                  {slaveAppId}
                </option>
              ))}
              {availableSlaveAppIds.length === 0 && <option value="">No slave apps</option>}
            </select>
          </label>
        </div>

        <div className="panel callPanel">
          <label>
            <span>Handler</span>
            <input value={handlerType} onChange={(event) => setHandlerType(event.target.value)} />
          </label>
          <label>
            <span>JSON input</span>
            <textarea value={requestJson} onChange={(event) => setRequestJson(event.target.value)} rows={7} />
          </label>
          <label>
            <span>Files</span>
            <input
              type="file"
              multiple
              onChange={(event) => setSelectedFiles(Array.from(event.target.files ?? []))}
            />
          </label>
          <button type="button" className="primaryButton" onClick={sendCall} disabled={busy || !connected || !handlerType.trim()}>
            <Send size={17} aria-hidden="true" />
            <span>Call</span>
          </button>
          <pre className="resultBox">{resultJson || 'No result yet.'}</pre>
          <div className="fileResults">
            {resultFiles.map((file) => (
              <a key={file.id} className="fileResult" href={file.url} download={file.name || file.id}>
                <span>{file.name || file.id}</span>
                <span>{formatBytes(file.size)}</span>
                {file.isImage && <img src={file.url} alt={file.name || file.id} />}
              </a>
            ))}
          </div>
        </div>
      </section>

      <section className="lowerGrid">
        <div className="panel">
          <h2>Workers</h2>
          <div className="table">
            <div className="tableHead">
              <span>Name</span>
              <span>Status</span>
              <span>Apps</span>
              <span>Sessions</span>
            </div>
            {workers.map((worker) => (
              <button
                type="button"
                key={worker.id}
                className={worker.id === selectedWorkerId ? 'workerRow selected' : 'workerRow'}
                onClick={() => selectWorker(worker)}
              >
                <span>{worker.worker_name}</span>
                <span>{worker.status}</span>
                <span>{worker.slave_app_ids.join(', ') || '-'}</span>
                <span>{worker.active_session_count}</span>
              </button>
            ))}
            {workers.length === 0 && <p className="emptyText">No connected workers.</p>}
          </div>
        </div>

        <div className="panel">
          <h2>Session</h2>
          <dl className="details">
            <div>
              <dt>Session ID</dt>
              <dd>{session?.session_id || '-'}</dd>
            </div>
            <div>
              <dt>Worker ID</dt>
              <dd>{session?.worker_session_id || selectedWorkerId || '-'}</dd>
            </div>
            <div>
              <dt>Slave app</dt>
              <dd>{session?.slave_app_id || selectedSlaveAppId || '-'}</dd>
            </div>
            <div>
              <dt>Expires</dt>
              <dd>{session?.expires_at || '-'}</dd>
            </div>
          </dl>
        </div>

        <div className="panel">
          <h2>Log</h2>
          <ol className="logList">
            {logs.map((item) => (
              <li key={item.id}>{item.message}</li>
            ))}
            {logs.length === 0 && <li>Ready.</li>}
          </ol>
        </div>
      </section>
    </main>
  );
}

function pickSlaveAppId(worker: WorkerSessionView, current: string): string {
  if (worker.slave_app_ids.includes(current)) {
    return current;
  }
  if (worker.slave_app_ids.includes('echo')) {
    return 'echo';
  }
  return worker.slave_app_ids[0] ?? '';
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
