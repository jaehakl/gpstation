'use client';

import { PlugZap, RefreshCw, Send, Square, Wifi } from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import {
  GpStationClient,
  GpStationPeer,
  ReceivedFile,
  SessionDescriptor,
  LauncherSessionView,
} from '@gpstation/v1-master-js-sdk';

const defaultApiBaseUrl = process.env.NEXT_PUBLIC_GPSTATION_V1_API_URL || '';
const defaultAccessToken = process.env.NEXT_PUBLIC_GPSTATION_V1_ACCESS_TOKEN || '';

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
  const [token, setToken] = useState(defaultAccessToken);
  const [launchers, setLaunchers] = useState<LauncherSessionView[]>([]);
  const [selectedLauncherId, setSelectedLauncherId] = useState('');
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
  const selectedLauncher = launchers.find((launcher) => launcher.id === selectedLauncherId);
  const availableSlaveAppIds = selectedLauncher?.slave_app_ids ?? [];

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

  async function refreshLaunchers() {
    setBusy(true);
    try {
      const nextLaunchers = await client.listLaunchers();
      setLaunchers(nextLaunchers);
      const nextSelectedLauncher = nextLaunchers.find((launcher) => launcher.id === selectedLauncherId) ?? nextLaunchers[0];
      if (nextSelectedLauncher) {
        setSelectedLauncherId(nextSelectedLauncher.id);
        setSelectedSlaveAppId(pickSlaveAppId(nextSelectedLauncher, selectedSlaveAppId));
      }
      setStatus('launchers refreshed');
      addLog(`launchers: ${nextLaunchers.length}`);
    } catch (error) {
      setStatus('launcher refresh failed');
      addLog(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function connect() {
    if (!selectedLauncherId) {
      setStatus('select launcher');
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
        launcherSessionId: selectedLauncherId,
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

  function selectLauncher(launcher: LauncherSessionView) {
    setSelectedLauncherId(launcher.id);
    setSelectedSlaveAppId(pickSlaveAppId(launcher, selectedSlaveAppId));
  }

  return (
    <main className="shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">GP Station v1</p>
          <h1>Launcher DataChannel Console</h1>
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
            <button type="button" onClick={refreshLaunchers} disabled={busy} title="Refresh launchers">
              <RefreshCw size={17} aria-hidden="true" />
              <span>Refresh</span>
            </button>
            <button type="button" onClick={connect} disabled={busy || !selectedLauncherId || !selectedSlaveAppId} title="Connect">
              <PlugZap size={17} aria-hidden="true" />
              <span>Connect</span>
            </button>
            <button type="button" onClick={disconnect} title="Disconnect">
              <Square size={17} aria-hidden="true" />
              <span>Close</span>
            </button>
          </div>
          <label>
            <span>Launcher</span>
            <select
              value={selectedLauncherId}
              onChange={(event) => {
                const launcher = launchers.find((item) => item.id === event.target.value);
                if (launcher) {
                  selectLauncher(launcher);
                } else {
                  setSelectedLauncherId('');
                  setSelectedSlaveAppId('');
                }
              }}
            >
              <option value="">No launcher selected</option>
              {launchers.map((launcher) => (
                <option key={launcher.id} value={launcher.id}>
                  {launcher.launcher_name} | {launcher.status} | {launcher.id.slice(0, 8)}
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
          <h2>Launchers</h2>
          <div className="table">
            <div className="tableHead">
              <span>Name</span>
              <span>Status</span>
              <span>Apps</span>
              <span>Sessions</span>
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
                <span>{launcher.active_session_count}</span>
              </button>
            ))}
            {launchers.length === 0 && <p className="emptyText">No connected launchers.</p>}
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
              <dt>Launcher ID</dt>
              <dd>{session?.launcher_session_id || selectedLauncherId || '-'}</dd>
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

function pickSlaveAppId(launcher: LauncherSessionView, current: string): string {
  if (launcher.slave_app_ids.includes(current)) {
    return current;
  }
  if (launcher.slave_app_ids.includes('echo')) {
    return 'echo';
  }
  return launcher.slave_app_ids[0] ?? '';
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
