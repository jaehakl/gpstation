# GP Station v1 Website

OAuth/JWT 관리 콘솔입니다. 계정, Access Token, Launcher, SlaveSession 상태를 브라우저에서 관리합니다.

## Install

```powershell
cd app_v1/masters/website
npm install
```

## Run

```powershell
cd app_v1/masters/website
npm run dev
```

기본 포트는 `3002`입니다.

## Environment

```text
NEXT_PUBLIC_GPSTATION_V1_API_URL=http://localhost:8100
```

서버에는 Google OAuth 설정이 필요합니다.

```text
GPSTATION_V1_APP_BASE_URL=http://localhost:3002
GPSTATION_V1_GOOGLE_CLIENT_ID=
GPSTATION_V1_GOOGLE_CLIENT_SECRET=
GPSTATION_V1_GOOGLE_REDIRECT_URI=http://localhost:8100/web/auth/google/callback
GPSTATION_V1_JWT_SECRET=change-this-to-a-long-random-secret
```

신규 OAuth 사용자는 `unauthorized`로 생성됩니다. 첫 관리자는 DB에서 직접 승격합니다.

```sql
UPDATE users SET role = 'admin' WHERE email = '<admin email>';
```
