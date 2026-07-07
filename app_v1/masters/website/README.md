# GP Station v1 Website

Google OAuth 로그인, JWT 쿠키 세션, Access Token 발급, 사용자 관리, Launcher와 SlaveSession 관리를 제공하는 Next.js 콘솔입니다.

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

개발 및 운영 포트는 `3000`입니다. API URL은 `.env`에 명시해야 합니다.

```text
NEXT_PUBLIC_GPSTATION_V1_API_URL=https://gps.qutat.com
```

로컬에서 실행할 때도 `app_v1/masters/website/.env`를 만들고 명시적으로 값을 넣습니다. 서버도 `app_v1/server/.env`에 Google OAuth, JWT, DB, CORS 값을 모두 설정해야 시작됩니다.

Google Cloud Console production 설정:

```text
Authorized JavaScript origin: https://gps.qutat.com
Authorized redirect URI: https://gps.qutat.com/web/auth/google/callback
```

새 OAuth 사용자는 `unauthorized`로 생성됩니다. 첫 관리자는 DB에서 직접 승격합니다.

```sql
UPDATE users SET role = 'admin' WHERE email = '<admin email>';
```
