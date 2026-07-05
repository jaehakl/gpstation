'use client';

import { PlugZap, RefreshCw, Send, Square, Wifi } from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import {
  GpStationClient,
  GpStationPeer,
  SessionDescriptor,
  WorkerSessionView,
} from '@gpstation/v1-js-sdk';

const defaultApiBaseUrl = process.env.NEXT_PUBLIC_GPSTATION_V1_API_URL || 'http://127.0.0.1:8100';

type LogItem = {
  id: number;
  message: string;
};

export default function Home() {
  const [apiBaseUrl, setApiBaseUrl] = useState(defaultApiBaseUrl);
  const [token, setToken] = useState('demo-client-token');
  const [workers, setWorkers] = useState<WorkerSessionView[]>([]);
  const [selectedWorkerId, setSelectedWorkerId] = useState('');
  const [session, setSession] = useState<SessionDescriptor | null>(null);
  const [status, setStatus] = useState('idle');
  const [echoText, setEchoText] = useState('hello gp station');
  const [echoResult, setEchoResult] = useState('');
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

  function addLog(message: string) {
    const id = logIdRef.current + 1;
    logIdRef.current = id;
    setLogs((items) => [{ id, message }, ...items].slice(0, 12));
  }

  async function refreshWorkers() {
    setBusy(true);
    try {
      const nextWorkers = await client.listWorkers();
      setWorkers(nextWorkers);
      if (!selectedWorkerId && nextWorkers[0]) {
        setSelectedWorkerId(nextWorkers[0].id);
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
    setBusy(true);
    setEchoResult('');
    peerRef.current?.close();
    peerRef.current = null;
    setConnected(false);
    try {
      const descriptor = await client.createSession({ workerSessionId: selectedWorkerId });
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

  async function sendEcho() {
    const peer = peerRef.current;
    if (!peer) {
      setStatus('not connected');
      return;
    }
    setBusy(true);
    try {
      const result = await peer.echo({ text: echoText, sent_at: new Date().toISOString() });
      setEchoResult(JSON.stringify(result, null, 2));
      addLog('echo.result');
    } catch (error) {
      setStatus('echo failed');
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
            <button type="button" onClick={connect} disabled={busy || !selectedWorkerId} title="Connect">
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
            <select value={selectedWorkerId} onChange={(event) => setSelectedWorkerId(event.target.value)}>
              <option value="">No worker selected</option>
              {workers.map((worker) => (
                <option key={worker.id} value={worker.id}>
                  {worker.worker_name} · {worker.status} · {worker.id.slice(0, 8)}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="panel echoPanel">
          <label>
            <span>Echo payload</span>
            <textarea value={echoText} onChange={(event) => setEchoText(event.target.value)} rows={6} />
          </label>
          <button type="button" className="primaryButton" onClick={sendEcho} disabled={busy || !connected}>
            <Send size={17} aria-hidden="true" />
            <span>Send Echo</span>
          </button>
          <pre className="resultBox">{echoResult || 'No echo result yet.'}</pre>
        </div>
      </section>

      <section className="lowerGrid">
        <div className="panel">
          <h2>Workers</h2>
          <div className="table">
            <div className="tableHead">
              <span>Name</span>
              <span>Status</span>
              <span>Sessions</span>
            </div>
            {workers.map((worker) => (
              <button
                type="button"
                key={worker.id}
                className={worker.id === selectedWorkerId ? 'workerRow selected' : 'workerRow'}
                onClick={() => setSelectedWorkerId(worker.id)}
              >
                <span>{worker.worker_name}</span>
                <span>{worker.status}</span>
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
