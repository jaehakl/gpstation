import { Cable, ListChecks, RefreshCw } from 'lucide-react';
import type { CandidateSummary, ConnectDiagnosticEvent } from '@gpstation/v1-master-js-sdk';

import { formatDuration } from '../format';
import type { AiSession } from '../useAiSession';

export function ConnectionPanel({ session, active }: { session: AiSession; active: boolean }) {
  if (!active) {
    return null;
  }

  const aiLaunchers = session.launchers.filter((launcher) => launcher.slave_app_ids.includes('ai'));
  const selectedLauncher = session.launchers.find((launcher) => launcher.id === session.selectedLauncherId);

  return (
    <>
      <section className="controlBand">
        <label>
          <span>Server</span>
          <input value={session.apiBaseUrl} onChange={(event) => session.setApiBaseUrl(event.target.value)} />
        </label>
        <label>
          <span>Token (runtime only)</span>
          <input
            type="password"
            autoComplete="off"
            value={session.token}
            onChange={(event) => session.setToken(event.target.value)}
            placeholder="Enter a client-scope token"
          />
        </label>
        <label>
          <span>ICE Servers JSON</span>
          <textarea
            className="compactTextarea"
            value={session.rtcIceServersJson}
            onChange={(event) => session.setRtcIceServersJson(event.target.value)}
            rows={3}
            placeholder='[{"urls":"stun:stun.l.google.com:19302"}]'
          />
        </label>
        <label>
          <span>AI Launcher Reference</span>
          <select value={session.selectedLauncherId} onChange={(event) => session.setSelectedLauncherId(event.target.value)}>
            <option value="">No launcher selected</option>
            {aiLaunchers.map((launcher) => (
              <option key={launcher.id} value={launcher.id}>
                {launcher.launcher_name} | {launcher.status} | {launcher.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
        <div className="buttonCluster">
          <button
            type="button"
            onClick={() => {
              void session.refreshLaunchers();
            }}
            disabled={session.busy}
            title="Refresh launchers"
          >
            <RefreshCw size={17} aria-hidden="true" />
            <span>Refresh</span>
          </button>
        </div>
      </section>

      <section className="tabGrid connectionGrid">
        <div className="panel">
          <div className="panelHeader">
            <h2>Launchers</h2>
            <span>{session.launchers.length}</span>
          </div>
          <div className="table">
            <div className="tableHead">
              <span>Name</span>
              <span>Status</span>
              <span>Apps</span>
            </div>
            {session.launchers.map((launcher) => (
              <button
                type="button"
                key={launcher.id}
                className={launcher.id === session.selectedLauncherId ? 'launcherRow selected' : 'launcherRow'}
                onClick={() => session.setSelectedLauncherId(launcher.id)}
              >
                <span>{launcher.launcher_name}</span>
                <span>{launcher.status}</span>
                <span>{launcher.slave_app_ids.join(', ') || '-'}</span>
              </button>
            ))}
            {session.launchers.length === 0 ? <p className="emptyText">No connected launchers.</p> : null}
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
                <dd>{session.currentJob?.id || '-'}</dd>
              </div>
              <div>
                <dt>Assigned Launcher</dt>
                <dd>{session.currentJob?.launcher_id || '-'}</dd>
              </div>
              <div>
                <dt>Slave App</dt>
                <dd>{session.currentJob?.slave_app_id || 'ai'}</dd>
              </div>
              <div>
                <dt>State</dt>
                <dd>{session.currentJob?.state || 'idle'}</dd>
              </div>
              <div>
                <dt>Network Prewarm</dt>
                <dd>{session.prewarmStatus}</dd>
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
              {session.logs.map((item) => (
                <li key={item.id}>{item.message}</li>
              ))}
              {session.logs.length === 0 ? <li>Ready.</li> : null}
            </ol>
          </div>

          <div className="panel diagnosticPanel">
            <div className="panelHeader">
              <h2>WebRTC Diagnostics</h2>
              <Cable size={17} aria-hidden="true" />
            </div>
            <ol className="logList diagnosticList">
              {session.diagnostics.map((item) => (
                <li key={item.id}>
                  <strong>{item.time}</strong> {item.message}
                  <span>{formatDiagnosticState(item)}</span>
                  {item.prewarmHit !== undefined ||
                  item.offerGatheringMs !== undefined ||
                  item.answerWaitMs !== undefined ||
                  item.dataChannelOpenMs !== undefined ||
                  item.elapsedMs !== undefined ? (
                    <span>
                      {[
                        item.prewarmHit !== undefined ? `prewarm=${item.prewarmHit ? 'hit' : 'miss'}` : '',
                        item.offerGatheringMs !== undefined ? `offer=${formatDuration(item.offerGatheringMs)}` : '',
                        item.answerWaitMs !== undefined ? `answer=${formatDuration(item.answerWaitMs)}` : '',
                        item.dataChannelOpenMs !== undefined
                          ? `datachannel=${formatDuration(item.dataChannelOpenMs)}`
                          : '',
                        item.elapsedMs !== undefined ? `elapsed=${formatDuration(item.elapsedMs)}` : '',
                      ]
                        .filter(Boolean)
                        .join(' / ')}
                    </span>
                  ) : null}
                  {item.localCandidateSummary ? (
                    <span>local: {formatCandidateSummary(item.localCandidateSummary)}</span>
                  ) : null}
                  {item.remoteCandidateSummary ? (
                    <span>remote: {formatCandidateSummary(item.remoteCandidateSummary)}</span>
                  ) : null}
                </li>
              ))}
              {session.diagnostics.length === 0 ? <li>No WebRTC diagnostics yet.</li> : null}
            </ol>
            <details className="sdpDetails">
              <summary>Local offer SDP</summary>
              <pre className="sdpBox">{session.localSdp || 'No local offer yet.'}</pre>
            </details>
            <details className="sdpDetails">
              <summary>Remote answer SDP</summary>
              <pre className="sdpBox">{session.remoteSdp || 'No remote answer yet.'}</pre>
            </details>
          </div>
        </div>
      </section>
    </>
  );
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
