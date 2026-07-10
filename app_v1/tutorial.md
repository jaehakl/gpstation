# GP Station v1 Tutorial

이 문서는 `app_v1`의 현재 job 기반 실행 흐름을 빠르게 따라가기 위한 안내입니다. 오래된 세션/signaling 모드는 제거되었고, 기본 slave app은 `ai`입니다.

## 1. 구성 요소

- `server/`: FastAPI 서버입니다. 사용자, Access Token, Launcher, Job을 DB에 저장하고 `/v1/jobs`와 `/v1/launchers/control`을 제공합니다.
- `launcher/`: 사용자의 머신에서 실행됩니다. 서버 control WebSocket에 연결하고, `slaves/ai` worker subprocess를 유지하면서 job을 실행합니다.
- `sdk/`: Python slave runtime과 공통 protocol model을 제공합니다.
- `sdk/master/js/`: 브라우저 master용 TypeScript SDK입니다. `runJob`과 job 조회 API를 제공합니다.
- `slaves/ai/`: `ai.llm`, `ai.chat`, `ai.embeddings`, `ai.sdxl.t2i` handler를 제공하는 기본 slave app입니다.
- `masters/ai/`: AI job 흐름을 브라우저에서 테스트하는 Vite 앱입니다.
- `website/`: Google OAuth 로그인, Access Token 발급, Launcher/Job 관리 콘솔입니다.

## 2. 로컬 실행 순서

```powershell
cd app_v1/server
poetry install
poetry run alembic upgrade head
poetry run gpstation-v1-server
```

```powershell
cd app_v1/slaves/ai
poetry install
```

```powershell
cd app_v1/launcher
poetry install
poetry run launcher
```

```powershell
cd app_v1/website
npm install
npm run dev
```

```powershell
cd app_v1/sdk/master/js
npm ci
npm run build

cd ../../../masters/ai
npm install
npm run dev
```

웹사이트에서 `launcher` scope Access Token을 만들어 launcher `.env`에 넣고, `client` scope Access Token은 AI master 실행 화면에 직접 입력합니다. 브라우저 토큰은 Vite 환경변수나 빌드 결과에 포함하지 않습니다.

## 3. Job 생성 흐름

브라우저 master는 JS SDK의 `runJob`을 호출합니다.

```ts
const result = await client.runJob(
  'ai.llm',
  {
    prompt: '짧게 자기소개를 해줘',
    max_tokens: 128,
  },
  { slaveAppId: 'ai' },
);
```

Streaming chat처럼 같은 WebRTC job session에서 이어지는 호출이 필요하면 `autoFinish:false`로 session을 유지합니다.

```ts
const first = await client.runJob(
  'ai.chat',
  {
    system_prompt: '친절하게 답하세요.',
    prompt: '짧게 자기소개를 해줘',
    max_tokens: 128,
  },
  {
    slaveAppId: 'ai',
    autoFinish: false,
    onEvent: (event) => {
      if (event.type === 'ai.chat.delta') {
        console.log(event.payload);
      }
    },
  },
);

const followup = await first.session.call('ai.chat', {
  prompt: '방금 답변을 한 문장으로 요약해줘',
});

console.log(followup.payload.remaining_tokens);

await first.session.finish();
```

SDK는 WebRTC offer를 만든 뒤 `POST /v1/jobs`로 job을 생성합니다. 서버는 사용자의 idle launcher를 찾아 `job.start` control message를 보냅니다.

Launcher는 필요한 slave app worker가 없으면 `slaves/ai` subprocess를 `--worker` 모드로 시작합니다. Worker가 `worker.ready`를 보내면 launcher는 job payload를 worker stdin으로 전달하고, worker가 만든 answer/result/progress/error를 서버와 브라우저로 중계합니다.

## 4. 주요 API

- `POST /v1/jobs`: job 생성
- `GET /v1/jobs/{job_id}`: job 상태 조회
- `GET /v1/jobs/{job_id}/wait-answer`: answer 준비 대기
- `POST /v1/jobs/{job_id}/kill`: job 취소 요청
- `GET /v1/launchers`: 사용 가능한 launcher 조회
- `WS /v1/launchers/control`: launcher control WebSocket

## 5. Control Protocol

서버에서 launcher로 보내는 주요 메시지:

- `job.start`
- `job.cancel`
- `worker.reset`

Launcher에서 서버로 보내는 주요 메시지:

- `launcher.hello`
- `launcher.heartbeat`
- `job.answer`
- `job.running`
- `job.progress`
- `job.result`
- `job.error`
- `job.cancelled`
- `worker.reset.done`

## 6. DB 모델

현재 runtime DB의 핵심 테이블은 다음과 같습니다.

- `users`, `identities`, `sessions`, `oauth_states`, `auth_audit`: website auth
- `access_keys`: client/launcher programmatic auth
- `launchers`: 연결된 launcher의 DB 상태
- `jobs`: job 요청, 할당, 결과, 오류 상태

DB 구조 변경은 서버 시작 코드가 아니라 Alembic migration만 수행합니다. 서버는 시작 시 현재 schema revision을 검증하며, migration이 적용되지 않은 DB에서는 실행을 거부합니다.

## 7. 검증

```powershell
cd app_v1/server
poetry run pytest
```

```powershell
cd app_v1/launcher
poetry run pytest
```

```powershell
cd app_v1/sdk
python -m pytest
```

```powershell
cd app_v1/sdk/master/js
npm run typecheck
npm run build
```

```powershell
cd app_v1/masters/ai
npm run typecheck
npm run build
```

```powershell
cd app_v1/website
npm run typecheck
npm run build
```
