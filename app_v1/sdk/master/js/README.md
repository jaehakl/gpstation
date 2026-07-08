# GP Station v1 Master JS SDK

Browser TypeScript SDK for the master side of the v1 job runtime.

Build it before running the AI master app:

```powershell
cd app_v1/sdk/master/js
npm install --no-package-lock
npm run build
```

```ts
import { GpStationClient } from '@gpstation/v1-master-js-sdk';

const client = new GpStationClient({
  apiBaseUrl: 'https://gps.qutat.com',
  token: process.env.GPSTATION_V1_ACCESS_TOKEN!,
});

const launchers = await client.listLaunchers();
console.log(launchers);

const result = await client.runJob(
  'ai.llm',
  {
    prompt: 'hello',
    max_tokens: 128,
  },
  { slaveAppId: 'ai' },
);

console.log(result.payload);
```

`runJob` uses a long-lived WebRTC job protocol internally. By default it sends one handler call and automatically finishes the job. To keep the DataChannel open for more calls, set `autoFinish: false` and finish the returned session explicitly:

```ts
const first = await client.runJob(
  'ai.llm',
  { prompt: 'hello' },
  { slaveAppId: 'ai', autoFinish: false },
);

const embedding = await first.session.call('ai.embeddings', {
  text: 'hello',
});

await first.session.finish();

console.log(first.payload, embedding.payload);
```

Handlers can push DataChannel-only events during a call. Use `onEvent` on `runJob` or `session.call` to render streamed progress without waiting for the final result.
