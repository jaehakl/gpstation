# GP Station v1 Website

Google OAuth 로그인, JWT 쿠키 세션, Access Token 발급, 사용자 관리, Launcher와 Job 관리를 제공하는 Vite 기반 React 콘솔입니다.

## Install

```powershell
cd app_v1/website
npm install
```

## Run

```powershell
cd app_v1/website
npm run dev
```

개발 서버는 `127.0.0.1:3000`에서 실행됩니다. API URL은 `.env`에 명시합니다.

```text
VITE_GPSTATION_V1_API_URL=https://gps.qutat.com
```

로컬 서버를 직접 호출하려면 서버 CORS 설정에 website origin을 추가한 뒤 다음처럼 설정할 수 있습니다.

```text
VITE_GPSTATION_V1_API_URL=http://localhost:8000
```

운영에서는 `npm run build`로 생성되는 `dist` 디렉터리를 `/var/www/gpstation-v1`로 publish하고, Nginx가 그 디렉터리를 정적 파일로 직접 서빙합니다. 별도 website Node/systemd 서비스는 사용하지 않습니다.

`/chat` 설정에서는 thinking 사용 여부, LOW/DEFAULT effort, Text/JSON 응답 형식을 선택할 수 있습니다. Chat 요청은 canonical `think` 필드를 사용하며, AI slave가 reasoning을 제거한 final 답변만 stream과 대화 기록에 표시합니다.

Google Cloud Console production 설정:

```text
Authorized JavaScript origin: https://gps.qutat.com
Authorized redirect URI: https://gps.qutat.com/web/auth/google/callback
```

새 OAuth 사용자는 `unauthorized`로 생성됩니다. 첫 관리자는 DB에서 직접 승격합니다.

```sql
UPDATE users SET role = 'admin' WHERE email = '<admin email>';
```
