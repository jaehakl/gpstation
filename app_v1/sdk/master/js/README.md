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
const result = await client.runJob({
  launcherId: launchers[0].id,
  slaveAppId: 'ai',
  handlerType: 'ai.llm',
  payload: {
    prompt: 'hello',
    max_tokens: 128,
  },
});

console.log(result.payload);
```

The SDK keeps the browser-facing surface on `/v1/jobs`: `runJob`, `prewarmJobConnection`, `getJob`, `getJobLogs`, and `killJob`.
