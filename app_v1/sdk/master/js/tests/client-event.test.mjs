import assert from 'node:assert/strict';
import test from 'node:test';

import { GpStationClient, GpStationJobSession } from '../dist/client.js';
import { GpStationJobPeer } from '../dist/job-peer.js';

class FakePeer {
  closed = false;

  async call(_callId, _handlerType, _input, _timeoutMs, onEvent) {
    onEvent({ id: 'job-1', type: 'ai.chat.delta', payload: { delta: '안녕' } });
    return { type: 'ai.chat.result', payload: { answer: '안녕' } };
  }

  async finish() {}

  close() {
    this.closed = true;
  }
}

class FakePeerConnection {
  signalingState = 'stable';
  iceGatheringState = 'complete';
  iceConnectionState = 'connected';
  connectionState = 'connected';
  closed = false;

  close() {
    this.closed = true;
    this.signalingState = 'closed';
    this.iceConnectionState = 'closed';
    this.connectionState = 'closed';
  }
}

class FakeDataChannel extends EventTarget {
  binaryType = 'arraybuffer';
  readyState = 'open';
  bufferedAmount = 0;
  bufferedAmountLowThreshold = 0;
  sent = [];

  send(data) {
    this.sent.push(data);
  }

  dispatchMessage(data) {
    const event = new Event('message');
    Object.defineProperty(event, 'data', { value: data });
    this.dispatchEvent(event);
  }
}

function createJobPeer() {
  const peerConnection = new FakePeerConnection();
  const dataChannel = new FakeDataChannel();
  const diagnostics = [];
  const peer = new GpStationJobPeer(peerConnection, dataChannel, (event) => diagnostics.push(event));
  return { dataChannel, diagnostics, peer, peerConnection };
}

test('session call dispatches the same default and call onEvent once', async () => {
  const events = [];
  const onEvent = (event) => events.push(event);
  const session = new GpStationJobSession('job-1', new FakePeer(), 1000, onEvent);

  await session.call('ai.chat', { prompt: 'hello' }, { onEvent });

  assert.equal(events.length, 1);
  assert.deepEqual(events[0], { id: 'job-1', type: 'ai.chat.delta', payload: { delta: '안녕' } });
});

test('session call dispatches distinct default and call onEvent callbacks', async () => {
  const defaultEvents = [];
  const callEvents = [];
  const session = new GpStationJobSession(
    'job-1',
    new FakePeer(),
    1000,
    (event) => defaultEvents.push(event),
  );

  await session.call('ai.chat', { prompt: 'hello' }, { onEvent: (event) => callEvents.push(event) });

  assert.equal(defaultEvents.length, 1);
  assert.equal(callEvents.length, 1);
});

test('cookie auth requests include credentials without authorization header', async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return new Response(JSON.stringify([]), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  try {
    const client = new GpStationClient({
      apiBaseUrl: 'https://api.example.test/',
      authMode: 'cookie',
      jobApiPrefix: '/web/jobs',
    });

    await client.listLaunchers();
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'https://api.example.test/v1/launchers');
  assert.equal(calls[0].init.credentials, 'include');
  assert.equal(new Headers(calls[0].init.headers).has('Authorization'), false);
});

test('cookie auth unsafe web requests include csrf token', async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url, init });
    if (url === 'https://api.example.test/web/auth/csrf') {
      return new Response(JSON.stringify({ csrf_token: 'csrf-1' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  try {
    const client = new GpStationClient({
      apiBaseUrl: 'https://api.example.test/',
      authMode: 'cookie',
      jobApiPrefix: '/web/jobs',
    });

    await client.request('/web/jobs', { method: 'POST', body: '{}' });
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(calls.length, 2);
  assert.equal(calls[0].url, 'https://api.example.test/web/auth/csrf');
  assert.equal(calls[0].init.credentials, 'include');
  assert.equal(calls[1].url, 'https://api.example.test/web/jobs');
  assert.equal(calls[1].init.credentials, 'include');
  const headers = new Headers(calls[1].init.headers);
  assert.equal(headers.get('X-CSRF-Token'), 'csrf-1');
  assert.equal(headers.has('Authorization'), false);
});

test('cookie auth csrf token refreshes once after forbidden response', async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  let csrfCounter = 0;
  let postCounter = 0;
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url, init });
    if (url === 'https://api.example.test/web/auth/csrf') {
      csrfCounter += 1;
      return new Response(JSON.stringify({ csrf_token: `csrf-${csrfCounter}` }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    postCounter += 1;
    if (postCounter === 1) {
      return new Response(JSON.stringify({ detail: 'CSRF token required' }), {
        status: 403,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  try {
    const client = new GpStationClient({
      apiBaseUrl: 'https://api.example.test/',
      authMode: 'cookie',
      jobApiPrefix: '/web/jobs',
    });

    await client.request('/web/jobs/job-1/kill', { method: 'POST' });
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.deepEqual(
    calls.map((call) => call.url),
    [
      'https://api.example.test/web/auth/csrf',
      'https://api.example.test/web/jobs/job-1/kill',
      'https://api.example.test/web/auth/csrf',
      'https://api.example.test/web/jobs/job-1/kill',
    ],
  );
  assert.equal(new Headers(calls[1].init.headers).get('X-CSRF-Token'), 'csrf-1');
  assert.equal(new Headers(calls[3].init.headers).get('X-CSRF-Token'), 'csrf-2');
});

test('job peer finish resolves after job.finished ack', async () => {
  const { dataChannel, diagnostics, peer, peerConnection } = createJobPeer();

  const finished = peer.finish('job-1', 1000);
  dataChannel.dispatchMessage(JSON.stringify({ kind: 'job.finished', id: 'job-1' }));
  await finished;

  assert.deepEqual(JSON.parse(dataChannel.sent[0]), { kind: 'job.finish', id: 'job-1' });
  assert.equal(peerConnection.closed, true);
  assert.equal(diagnostics.at(-1).message, 'received job finished');
});

test('job peer finish resolves when data channel closes after finish frame is sent', async () => {
  const { dataChannel, diagnostics, peer, peerConnection } = createJobPeer();

  const finished = peer.finish('job-1', 1000);
  dataChannel.dispatchEvent(new Event('close'));
  await finished;

  assert.deepEqual(JSON.parse(dataChannel.sent[0]), { kind: 'job.finish', id: 'job-1' });
  assert.equal(peerConnection.closed, true);
  assert.equal(diagnostics.at(-1).message, 'job finish completed after data channel closed');
});

test('job peer finish resolves when data channel errors after finish frame is sent', async () => {
  const { dataChannel, diagnostics, peer, peerConnection } = createJobPeer();

  const finished = peer.finish('job-1', 1000);
  dataChannel.dispatchEvent(new Event('error'));
  await finished;

  assert.deepEqual(JSON.parse(dataChannel.sent[0]), { kind: 'job.finish', id: 'job-1' });
  assert.equal(peerConnection.closed, true);
  assert.equal(diagnostics.at(-1).message, 'job finish completed after data channel closed');
});

test('job peer call rejects when data channel errors before result', async () => {
  const { dataChannel, peer } = createJobPeer();

  const result = peer.call('job-1', 'ai.chat', { prompt: 'hello' }, 1000);
  dataChannel.dispatchEvent(new Event('error'));

  await assert.rejects(result, /data channel error/);
});
