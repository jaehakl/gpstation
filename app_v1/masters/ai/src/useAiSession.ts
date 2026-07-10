import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { GpStationClient, parseRtcIceServersJson } from '@gpstation/v1-master-js-sdk';
import type {
  CallResult,
  ConnectDiagnosticEvent,
  JobDescriptor,
  JobEvent,
  JobSession,
  LauncherView,
  RunJobSessionResult,
} from '@gpstation/v1-master-js-sdk';

import { formatClock, formatDurationSince } from './format';

const defaultApiBaseUrl = import.meta.env.VITE_GPSTATION_V1_API_URL || '';
const defaultRtcIceServersJson = import.meta.env.VITE_GPSTATION_V1_RTC_ICE_SERVERS_JSON || '';

type LogItem = {
  id: number;
  message: string;
};

type DiagnosticLogItem = ConnectDiagnosticEvent & {
  id: number;
  time: string;
};

export function useAiSession() {
  const [apiBaseUrl, setApiBaseUrl] = useState(defaultApiBaseUrl);
  const [token, setToken] = useState('');
  const [rtcIceServersJson, setRtcIceServersJson] = useState(defaultRtcIceServersJson);
  const [launchers, setLaunchers] = useState<LauncherView[]>([]);
  const [selectedLauncherId, setSelectedLauncherId] = useState('');
  const [currentJob, setCurrentJob] = useState<JobDescriptor | null>(null);
  const [status, setStatus] = useState('idle');
  const [busy, setBusy] = useState(false);
  const [logs, setLogs] = useState<LogItem[]>([]);
  const [diagnostics, setDiagnostics] = useState<DiagnosticLogItem[]>([]);
  const [localSdp, setLocalSdp] = useState('');
  const [remoteSdp, setRemoteSdp] = useState('');
  const [prewarmStatus, setPrewarmStatus] = useState('cold');
  const logIdRef = useRef(0);
  const diagnosticIdRef = useRef(0);

  const client = useMemo(
    () =>
      new GpStationClient({
        apiBaseUrl,
        token,
      }),
    [apiBaseUrl, token],
  );

  const readRtcConfig = useCallback(() => {
    const trimmed = rtcIceServersJson.trim();
    return trimmed ? { iceServers: parseRtcIceServersJson(trimmed) } : undefined;
  }, [rtcIceServersJson]);

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

  const prewarm = useCallback(
    (logStart = false) => {
      if (!apiBaseUrl.trim() || !token.trim()) {
        setPrewarmStatus('waiting for server/token');
        return;
      }
      try {
        client.prewarmJobConnection({
          slaveAppId: 'ai',
          rtcConfig: readRtcConfig(),
          onDiagnostic: addDiagnostic,
        });
        setPrewarmStatus('network warm');
        if (logStart) {
          addLog('network prewarm started');
        }
      } catch (error) {
        setPrewarmStatus('prewarm failed');
        addLog(`network prewarm failed: ${error instanceof Error ? error.message : String(error)}`);
      }
    },
    [addDiagnostic, addLog, apiBaseUrl, client, readRtcConfig, token],
  );

  useEffect(() => {
    client.clearPrewarmedJobConnections();
    const timer = window.setTimeout(() => prewarm(true), 0);
    return () => {
      window.clearTimeout(timer);
      client.clearPrewarmedJobConnections();
    };
  }, [client, prewarm]);

  function setCurrentJobState(state: string) {
    setCurrentJob((job) => (job ? { ...job, state } : job));
  }

  function startJob(handlerType: string) {
    setBusy(true);
    setDiagnostics([]);
    setLocalSdp('');
    setRemoteSdp('');
    setCurrentJob(null);
    addLog(`${formatClock(new Date())} ${handlerType} start`);
    return new Date();
  }

  function jobOptions(onEvent?: (event: JobEvent) => void) {
    return {
      slaveAppId: 'ai',
      rtcConfig: readRtcConfig(),
      onEvent,
      onJobCreated: (job: JobDescriptor) => {
        setCurrentJob(job);
        addLog(`job: ${job.id}`);
      },
      onStatus: (nextStatus: string) => {
        setStatus(nextStatus);
        if (nextStatus === 'waiting for answer') {
          setCurrentJobState('assigned');
        } else if (nextStatus === 'waiting for data channel') {
          setCurrentJobState('answer_ready');
        } else if (nextStatus === 'waiting for result') {
          setCurrentJobState('running');
        }
        addLog(nextStatus);
      },
      onDiagnostic: addDiagnostic,
    };
  }

  function completeJob(handlerType: string, startedAt: Date, state: 'running' | 'succeeded') {
    setCurrentJobState(state);
    setStatus(state === 'running' ? `${handlerType} response complete` : `${handlerType} complete`);
    addLog(`${formatClock(new Date())} ${handlerType} complete (${formatDurationSince(startedAt)})`);
  }

  function failJob(error: unknown, handlerType: string, startedAt?: Date) {
    const suffix = startedAt ? ` (${formatDurationSince(startedAt)})` : '';
    setCurrentJobState('failed');
    reportError(error, handlerType, suffix);
  }

  function reportError(error: unknown, handlerType: string, suffix = '') {
    setStatus(`${handlerType} failed`);
    addLog(`${formatClock(new Date())} ${handlerType} failed${suffix}`);
    addLog(error instanceof Error ? error.message : String(error));
  }

  async function runJob<TPayload, TResult>(
    handlerType: string,
    payload: TPayload,
    timeoutMs: number,
    onEvent?: (event: JobEvent) => void,
  ): Promise<CallResult<TResult>> {
    const startedAt = startJob(handlerType);
    try {
      const result = await client.runJob<TPayload, TResult>(handlerType, payload, {
        ...jobOptions(onEvent),
        timeoutMs,
      });
      completeJob(handlerType, startedAt, 'succeeded');
      return result;
    } catch (error) {
      failJob(error, handlerType, startedAt);
      throw error;
    } finally {
      setBusy(false);
      prewarm();
    }
  }

  async function openJob<TPayload, TResult>(
    handlerType: string,
    payload: TPayload,
    timeoutMs: number,
    onEvent?: (event: JobEvent) => void,
  ): Promise<RunJobSessionResult<TResult>> {
    const startedAt = startJob(handlerType);
    try {
      const result = await client.runJob<TPayload, TResult>(handlerType, payload, {
        ...jobOptions(onEvent),
        timeoutMs,
        autoFinish: false,
      });
      completeJob(handlerType, startedAt, 'running');
      return result;
    } catch (error) {
      failJob(error, handlerType, startedAt);
      prewarm();
      throw error;
    } finally {
      setBusy(false);
    }
  }

  async function callSession<TPayload, TResult>(
    jobSession: JobSession,
    handlerType: string,
    payload: TPayload,
    timeoutMs: number,
    onEvent?: (event: JobEvent) => void,
  ): Promise<CallResult<TResult>> {
    const startedAt = new Date();
    setBusy(true);
    setStatus(`${handlerType} waiting for result`);
    setCurrentJobState('running');
    addLog(`${formatClock(startedAt)} ${handlerType} start`);
    try {
      const result = await jobSession.call<TPayload, TResult>(handlerType, payload, { timeoutMs, onEvent });
      completeJob(handlerType, startedAt, 'running');
      return result;
    } catch (error) {
      failJob(error, handlerType, startedAt);
      throw error;
    } finally {
      setBusy(false);
    }
  }

  async function finishSession(jobSession: JobSession, handlerType: string, timeoutMs: number) {
    const startedAt = new Date();
    setBusy(true);
    setStatus(`${handlerType} closing`);
    addLog(`${formatClock(startedAt)} ${handlerType} finish`);
    try {
      await jobSession.finish({ timeoutMs });
      completeJob(handlerType, startedAt, 'succeeded');
    } catch (error) {
      jobSession.close();
      failJob(error, handlerType, startedAt);
      throw error;
    } finally {
      setBusy(false);
      prewarm();
    }
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
      setSelectedLauncherId(nextSelectedLauncher?.id ?? '');
      setStatus('launchers refreshed');
      addLog(
        `launchers: ${nextLaunchers.length} / ai-capable: ${nextLaunchers.filter((launcher) => launcher.slave_app_ids.includes('ai')).length}`,
      );
    } catch (error) {
      reportError(error, 'launcher refresh');
    } finally {
      setBusy(false);
    }
  }

  return {
    apiBaseUrl,
    setApiBaseUrl,
    token,
    setToken,
    rtcIceServersJson,
    setRtcIceServersJson,
    client,
    launchers,
    selectedLauncherId,
    setSelectedLauncherId,
    currentJob,
    status,
    busy,
    logs,
    diagnostics,
    localSdp,
    remoteSdp,
    prewarmStatus,
    refreshLaunchers,
    runJob,
    openJob,
    callSession,
    finishSession,
    reportError,
  };
}

export type AiSession = ReturnType<typeof useAiSession>;
