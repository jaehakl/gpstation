# GP Station v1 Example Web

Browser demo for the v1 MVP.

## Install and Run

```powershell
cd app_v1/sdk/js
npm install --no-package-lock
npm run build

cd app_v1/example/web
npm install
npm run dev
```

Open `http://127.0.0.1:3001`, use `demo-client-token`, refresh workers, choose a worker, connect, and send an echo message.

The dev server uses Webpack because Next 16 Turbopack currently does not resolve this local scoped `file:` SDK dependency reliably.
