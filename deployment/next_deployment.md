# Next 기반 배포 안내

이 문서는 기존 Vite 배포 흐름을 Next 기반 `apps/neo/ui` 구조에 맞게 옮긴 지침입니다.

- 공개 홈페이지: `https://www.onigiri.kr/`
- API: `https://www.onigiri.kr/api/*`
- FastAPI 내부 포트: `127.0.0.1:8000`
- Next 내부 포트: `127.0.0.1:3000`

# 0) 준비물

- 보유 도메인
  - `www.onigiri.kr`
  - `onigiri.kr`
- 코드 레포 (FastAPI + Next)
- Google OAuth 2.0 프로덕션 설정
  - Authorized JavaScript origins:
    - `https://www.onigiri.kr`
  - Authorized redirect URIs:
    - `https://www.onigiri.kr/api/auth/google/callback`
- backend.env 및 frontend.env
- Next 서버용 `deployment/app.conf`

```env
# backend.env
GOOGLE_REDIRECT_URI=https://www.onigiri.kr/api/auth/google/callback
APP_BASE_URL=https://www.onigiri.kr
COOKIE_DOMAIN=www.onigiri.kr

# frontend.env
NEXT_PUBLIC_API_BASE_URL=/api
API_INTERNAL_BASE_URL=http://127.0.0.1:8000
API_PROXY_TARGET=http://127.0.0.1:8000
```

# 1) Lightsail 인스턴스 만들기 & 고정 IP & 방화벽

1. Lightsail에서 최신 Ubuntu LTS 인스턴스를 생성합니다.
2. Static IP를 인스턴스에 붙입니다.
3. Lightsail 네트워킹 탭에서 22, 80, 443만 엽니다.
4. 8000과 3000은 외부에 열지 않습니다. 둘 다 Nginx 뒤에서 로컬로만 리슨합니다.

# 2) 도메인 연결

- `A` 레코드: `onigiri.kr` → Lightsail Static IP
- `A` 레코드 또는 `CNAME` 레코드: `www.onigiri.kr` → Lightsail Static IP 또는 `onigiri.kr`
- 전파 확인:

```bash
nslookup onigiri.kr
nslookup www.onigiri.kr
```

# 3) 서버 기본 셋업

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install nginx certbot python3-certbot-nginx git python3-venv build-essential curl

# Node, npm 설치
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install --lts
node -v && npm -v

# Poetry 설치
curl -sSL https://install.python-poetry.org | python3 -
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
poetry --version
```

# 4) 코드 가져오기 & 빌드

```bash
git clone <YOUR_REPO_URL> ~/onigiri
cp ~/backend.env ~/onigiri/apps/neo/api/.env
cp ~/frontend.env ~/onigiri/apps/neo/ui/.env

# 프론트엔드(Next) 빌드
cd ~/onigiri/apps/neo/ui
npm ci --workspaces=false
npm run build

# 백엔드(FastAPI) 설치 & 로컬 실행 테스트
cd ~/onigiri/apps/neo/api
poetry install
cd ~/onigiri/apps/neo/api/app
poetry run uvicorn main:app --host 127.0.0.1 --port 8000
```

Next는 `dist/`를 `/var/www`로 복사하지 않습니다. `.next/` 빌드 결과를 `next start`로 실행합니다.

# 5) systemd 서비스

## FastAPI 백엔드

`/etc/systemd/system/app-backend.service`

```ini
[Unit]
Description=FastAPI backend via poetry
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/onigiri/api
WorkingDirectory=/home/ubuntu/onigiri/apps/neo/api/app
EnvironmentFile=/home/ubuntu/onigiri/apps/neo/api/.env
ExecStart=/home/ubuntu/.local/bin/poetry run uvicorn main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips="*"
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

## Next 프론트엔드

`/etc/systemd/system/app-frontend.service`

```ini
[Unit]
Description=Next frontend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/onigiri/apps/neo/ui
EnvironmentFile=/home/ubuntu/onigiri/apps/neo/ui/.env
Environment=HOME=/home/ubuntu
Environment=NODE_ENV=production
ExecStart=/bin/bash -lc 'source /home/ubuntu/.nvm/nvm.sh && npm start'
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

서비스 등록:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now app-backend
sudo systemctl enable --now app-frontend
systemctl status app-backend --no-pager
systemctl status app-frontend --no-pager
```

# 6) Nginx 리버스 프록시

레이트리밋 존이 없다면 먼저 만듭니다.

`/etc/nginx/conf.d/ratelimit.conf`

```nginx
limit_req_zone $binary_remote_addr zone=req_per_ip:20m rate=17r/s;
limit_conn_zone $binary_remote_addr zone=conn_per_ip:20m;
```

`deployment/app.conf`는 Next 서버 기준입니다.

- `/api/` → `http://127.0.0.1:8000/`
- `/_next/static/` → `http://127.0.0.1:3000`
- `/`, `/context-play`, `/example-editor`, `/example-explorer`, 그 외 화면 경로 → `http://127.0.0.1:3000`

```bash
sudo cp ~/onigiri/deployment/app.conf /etc/nginx/sites-enabled/app.conf
sudo nginx -t && sudo systemctl reload nginx
```

# 7) HTTPS

```bash
sudo certbot --nginx -d www.onigiri.kr -d onigiri.kr
sudo certbot renew --dry-run
```
