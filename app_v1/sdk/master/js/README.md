# GP Station v1 Master JS SDK

Browser TypeScript SDK for the master side of the v1 MVP.

Build it before running the example web app:

```powershell
cd app_v1/sdk/master/js
npm install --no-package-lock
npm run build
```

```ts
const client = new GpStationClient({
  apiBaseUrl: 'http://127.0.0.1:8100',
  token: 'demo-client-token',
});

const launchers = await client.listLaunchers();
const session = await client.createSession({ launcherSessionId: launchers[0].id, slaveAppId: 'echo' });
const peer = await client.connectSession(session);
const file = new File(['hello file'], 'hello.txt', { type: 'text/plain' });
const result = await peer.call('echo.request', { text: 'hello' }, { files: [file] });

console.log(result.payload);
console.log(result.files[0]?.blob);
```
