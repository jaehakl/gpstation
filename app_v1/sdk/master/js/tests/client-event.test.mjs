import assert from 'node:assert/strict';
import test from 'node:test';

import { GpStationClient, GpStationJobSession } from '../dist/client.js';

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
