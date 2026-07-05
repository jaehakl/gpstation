# GP Station v1 JS SDK

Browser TypeScript SDK for the v1 MVP.

Build it before running the example web app:

```powershell
cd app_v1/sdk/js
npm install --no-package-lock
npm run build
```

```ts
const client = new GpStationClient({
  apiBaseUrl: 'http://127.0.0.1:8100',
  token: 'demo-client-token',
});

const workers = await client.listWorkers();
const session = await client.createSession({ workerSessionId: workers[0].id });
const peer = await client.connectSession(session);
const result = await peer.echo({ text: 'hello' });
```
