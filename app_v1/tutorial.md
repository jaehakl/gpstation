# GP Station v1 튜토리얼

## 1. 이 MVP가 하는 일

GP Station v1 MVP의 목표는 아주 좁고 명확합니다.

사용자가 자기 계정에 연결된 worker와 slave app을 고르고, master에서 세션을 만든 뒤, WebRTC DataChannel로 slave subprocess와 직접 통신하는 것까지 확인합니다. 지금은 실제 LLM이나 이미지 생성 작업 대신 `echo` slave app만 제공합니다. 즉 master가 `echo.request` handler를 JSON payload와 optional file attachments로 호출하면 slave subprocess가 같은 payload와 attachments를 `echo.result`로 돌려줍니다.

중요한 범위 제한도 있습니다.

- 서버 상태는 메모리에만 저장합니다.
- 사용자는 자기 소유 worker만 사용할 수 있습니다.
- 과금, marketplace, quota, persistent DB는 없습니다.
- 첫 master 클라이언트는 JS 브라우저입니다.
- Python master SDK는 REST scaffold만 있고 WebRTC master 기능은 후속 단계입니다.

## 2. 큰 그림

실행 중인 구성요소는 네 가지입니다.

```text
Master Example
  REST + signaling WebSocket
        |
        v
GP Station v1 Server
        ^
        |
  control WebSocket
Worker Main Process
        |
        | JSON-lines stdin/stdout
        v
Slave Subprocess

연결 완료 후:

Master Example <== WebRTC DataChannel ==> Slave Subprocess
```

여기서 헷갈리기 쉬운 점은 WebSocket과 WebRTC DataChannel이 둘 다 “양방향 통신”이라는 점입니다. 이 MVP에서 둘의 역할은 다릅니다.

- `control WebSocket`: worker main process가 서버에 계속 붙어 있는 관리 채널입니다.
- `signaling WebSocket`: master와 slave subprocess가 WebRTC 연결을 맺기 전 SDP offer/answer를 교환하는 임시 중계 채널입니다.
- `DataChannel`: WebRTC 연결이 끝난 뒤 master와 slave subprocess가 직접 메시지를 주고받는 실제 작업 채널입니다.

## 3. 폴더별 역할

`app_v1/`는 기존 `apps/`와 분리된 새 MVP입니다.

- `protocol/`: 서버, worker, SDK가 공유하는 메시지 이름과 Pydantic 모델
- `server/`: FastAPI 서버, 인증, worker/session registry, signaling relay
- `worker/`: worker main process와 built-in slave app plugins
- `sdk/master/js/`: 브라우저 master SDK
- `sdk/master/python/`: Python master SDK scaffold
- `sdk/slave/python/`: Python slave app authoring SDK/runtime
- `example/web/`: Next 기반 master 예제
- `scripts/`: smoke test와 local demo helper
- `plan.md`: 구현 계획과 현재 완료 상태

처음 코드를 읽는다면 이 순서가 좋습니다.

1. `protocol/gpstation_protocol/messages.py`
2. `server/gpstation_server/state.py`
3. `server/gpstation_server/main.py`
4. `worker/gpstation_worker_v1/control.py`
5. `worker/gpstation_worker_v1/subprocess_manager.py`
6. `worker/gpstation_worker_v1/slave_registry.py`
7. `sdk/master/js/src/index.ts`
8. `example/web/src/app/page.tsx`

## 4. 로컬 실행 방법

Python dependency:

```powershell
cd app_v1/server
poetry install

cd ../worker
poetry install

cd ../scripts
poetry install
```

`protocol/`은 서버와 worker가 Poetry editable path dependency로 자동 설치합니다. `app_v1/protocol`에서 직접 `poetry install`을 실행하는 경우는 protocol package 자체를 테스트하거나 수정할 때입니다. `sdk/master/python`도 현재 MVP 실행에는 필수가 아니며, Python master SDK를 개발하거나 확인할 때만 설치하면 됩니다.

Web dependency:

```powershell
cd app_v1/sdk/master/js
npm install --no-package-lock
npm run build

cd ../../../example/web
npm install --no-package-lock
```

실행 순서:

```powershell
cd app_v1/server
poetry run gpstation-v1-server
```

```powershell
cd app_v1/worker
poetry run gpstation-v1-worker
```

```powershell
cd app_v1/example/web
.\run.bat
```

기본 주소와 토큰:

- Server: `http://127.0.0.1:8100`
- Web: `http://localhost:3001`
- Client token: `demo-client-token`
- Worker token: `demo-worker-token`

브라우저에서 `http://localhost:3001`을 열고 다음 순서로 확인합니다.

1. Server에 `http://127.0.0.1:8100` 입력
2. Token에 `demo-client-token` 입력
3. `Refresh` 클릭
4. worker 선택
5. `echo` slave app 선택
6. `Connect` 클릭
7. Handler key와 JSON payload 입력
8. 필요하면 file attachments 선택
9. `Call Handler` 클릭

## 5. 요청 하나가 흐르는 과정

master 예제에서 `Connect`를 누르면 JS SDK가 먼저 서버에 세션 생성을 요청합니다.

```text
POST /v1/sessions
Authorization: Bearer demo-client-token

{
  "worker_session_id": "...",
  "slave_app_id": "echo",
  "ttl_seconds": null
}
```

이 요청은 `server/gpstation_server/main.py`의 `create_session()`으로 들어옵니다. 서버는 다음 일을 합니다.

1. token을 확인해서 사용자를 찾습니다.
2. `worker_session_id`가 같은 사용자 소유인지 확인합니다.
3. `slave_app_id`가 해당 worker가 광고한 app인지 확인합니다.
4. 메모리에 `ClientSession`을 만듭니다.
5. worker main process로 `session.start` 메시지를 보냅니다.
6. slave subprocess가 준비됐다는 `session.ready`를 기다립니다.
7. master에 signaling URL과 short-lived session token을 돌려줍니다.

서버가 돌려주는 응답은 이런 모양입니다.

```json
{
  "session_id": "...",
  "worker_session_id": "...",
  "slave_app_id": "echo",
  "signaling_url": "ws://127.0.0.1:8100/v1/sessions/.../signal?token=...",
  "token": "...",
  "expires_at": "..."
}
```

그다음 JS SDK는 WebRTC offer를 만들고 signaling WebSocket으로 보냅니다.

```text
Master -> Server -> Worker Main -> Slave Subprocess
```

slave subprocess는 offer를 받고 answer를 만듭니다. answer는 반대 방향으로 돌아옵니다.

```text
Slave Subprocess -> Worker Main -> Server -> Master
```

master가 answer를 적용하면 WebRTC 연결이 열리고, `gpstation.v1` DataChannel이 연결됩니다. 그 뒤부터는 서버가 작업 메시지를 중계하지 않습니다.

```text
Master <== DataChannel ==> Slave Subprocess
```

## 6. Protocol이 해주는 일

`protocol/gpstation_protocol/messages.py`에는 control message와 data channel message의 계약이 있습니다.

Control message 예:

- `worker.hello`
- `worker.heartbeat`
- `worker.accepted`
- `session.start`
- `session.ready`
- `signal.to_worker`
- `signal.to_client`
- `session.closed`
- `session.error`

DataChannel request control frame 예:

```json
{
  "kind": "call.request",
  "id": "message-id",
  "type": "echo.request",
  "payload": {
    "text": "hello"
  },
  "attachments": []
}
```

`echo` slave app은 응답으로 같은 `id`를 가진 `call.response` frame을 보냅니다.

```json
{
  "kind": "call.response",
  "id": "message-id",
  "type": "echo.result",
  "payload": {
    "text": "hello"
  },
  "attachments": []
}
```

파일, 이미지, Blob 같은 binary data는 JSON payload에 base64로 넣지 않습니다. 먼저 request/response control frame의 `attachments` metadata에 `{ id, name, mimeType, size }`를 싣고, 실제 bytes는 별도 binary chunk frame으로 보냅니다. 각 binary frame은 4-byte header length, UTF-8 JSON header, raw bytes 순서입니다.

메시지 모델을 따로 둔 이유는 서버, worker, master SDK, slave SDK가 같은 단어를 쓰게 만들기 위해서입니다. WebRTC와 WebSocket은 디버깅이 어려운 편이라, 메시지 이름이 흐트러지면 원인 찾기가 금방 지저분해집니다.

## 7. Server 코드 읽기

서버의 핵심은 두 파일입니다.

`server/gpstation_server/state.py`는 메모리 상태 저장소입니다.

- `WorkerConnection`: 현재 서버에 연결된 worker
- `ClientSession`: 브라우저가 만든 작업 세션
- `RuntimeState`: workers와 sessions를 관리하는 class

`RuntimeState`는 실제 DB가 아닙니다. 서버 프로세스가 종료되면 모든 worker/session 정보는 사라집니다. MVP에서는 E2E 연결을 증명하는 것이 목적이라 의도적으로 단순하게 두었습니다.

`server/gpstation_server/main.py`는 HTTP/WebSocket endpoint를 담습니다.

- `GET /health`: 서버 상태 확인
- `GET /v1/workers`: 현재 사용자 소유 worker 목록
- `POST /v1/sessions`: 선택한 slave app subprocess 시작 및 session descriptor 생성
- `WS /v1/workers/control`: worker main process가 붙는 control channel
- `WS /v1/sessions/{session_id}/signal`: 브라우저 signaling channel

인증은 `server/gpstation_server/auth.py`와 `settings.py`에 있습니다. 지금은 production 인증이 아니라 static bearer token map입니다.

기본값:

```text
demo-client-token -> user_id demo-user, scope client
demo-worker-token -> user_id demo-user, scope worker
```

서버는 `client` scope로 REST API를 열고, `worker` scope로 worker control WebSocket을 엽니다.

## 8. Worker 코드 읽기

worker는 main process와 slave subprocess로 나뉩니다.

### Worker main process

`worker/gpstation_worker_v1/control.py`가 서버의 `/v1/workers/control`에 연결합니다.

처음 연결되면 worker는 `worker.hello`를 보냅니다.

```json
{
  "type": "worker.hello",
  "worker_name": "...",
  "slave_app_ids": ["echo"],
  "metadata": {}
}
```

서버가 `worker.accepted`를 돌려주면 worker는 heartbeat를 보내며 대기합니다. 서버에서 `session.start`가 오면 `SessionManager`가 요청된 `slave_app_id`에 맞는 subprocess를 하나 띄웁니다.

### Subprocess manager

`worker/gpstation_worker_v1/subprocess_manager.py`는 세션별 slave subprocess를 관리합니다.

slave subprocess와는 stdin/stdout JSON-lines로 통신합니다. 한 줄에 JSON 객체 하나를 쓰는 방식입니다.

worker main이 slave subprocess에 보내는 메시지:

```json
{"type": "signal", "signal": {"type": "offer", "sdp": "..."}}
```

slave subprocess가 worker main에 보내는 메시지:

```json
{"type": "signal", "signal": {"type": "answer", "sdp": "..."}}
```

이 구조를 둔 이유는 나중에 실제 AI 작업 런타임을 slave app별 subprocess로 격리하기 위해서입니다. 세션이 끝나거나 timeout되면 해당 subprocess만 종료하면 됩니다.

### Slave subprocess

`worker/gpstation_worker_v1/slave_registry.py`는 요청된 `slave_app_id`의 manifest를 찾아 plugin module을 subprocess로 직접 실행합니다. plugin program은 `sdk/slave/python`의 `gpstation_slave_sdk_v1`를 import해서 `SlaveApp`, memory, initialize hook, handler들을 구성하고 `run_app(app)`을 호출합니다.

흐름은 다음과 같습니다.

1. `session.start`의 `slave_app_id`로 manifest registry 조회
2. manifest의 `module`을 `python -m ...` subprocess로 실행
3. plugin program이 slave SDK를 import하고 `SlaveApp` 구성
4. `initialize` hook 실행 후 `ready` 메시지를 stdout으로 emit
5. stdin에서 offer 수신 후 answer 생성
6. DataChannel message 수신
7. 등록된 plugin handler가 memory/context를 사용해 메시지를 처리하고 응답 전송

DataChannel label은 반드시 `gpstation.v1`이어야 합니다.

## 9. JS SDK와 Web 예제 코드 읽기

`sdk/master/js/src/index.ts`에는 master에서 쓰는 `GpStationClient`와 `GpStationPeer`가 있습니다.

`GpStationClient`가 하는 일:

- `listWorkers()`: `GET /v1/workers`
- `createSession()`: `POST /v1/sessions`
- `connectSession()`: signaling WebSocket 연결, WebRTC offer 생성, answer 적용, DataChannel open 대기

`GpStationPeer`가 하는 일:

- `call(handlerType, payload, options)`: DataChannel로 generic handler call 전송
- 같은 `id`의 `call.response`가 오고 attachment chunks가 모두 도착하면 Promise resolve
- `close()`: DataChannel, PeerConnection, WebSocket 정리

`example/web/src/app/page.tsx`는 SDK를 실제 화면에 연결합니다.

화면의 주요 state:

- `workers`: 서버에서 받은 worker 목록
- `selectedWorkerId`: 사용자가 고른 worker
- `selectedSlaveAppId`: 사용자가 고른 slave app
- `session`: 생성된 session descriptor
- `connected`: DataChannel 연결 여부
- `handlerType`, `requestJson`, `selectedFiles`, `resultJson`, `resultFiles`: handler call 입력/결과
- `logs`: 화면 하단 로그

## 10. Smoke test

REST smoke:

```powershell
cd app_v1/scripts
poetry run python smoke_rest.py http://127.0.0.1:8100 demo-client-token
```

서버가 살아 있고 worker 목록을 인증된 사용자 기준으로 볼 수 있으면 성공입니다.

WebRTC E2E smoke:

```powershell
cd app_v1/scripts
poetry run python smoke_aiortc_e2e.py http://127.0.0.1:8100 demo-client-token
```

성공하면 이런 결과가 나옵니다.

```json
{
  "worker_session_id": "...",
  "session_id": "...",
  "call": {
    "response": {
      "kind": "call.response",
      "id": "smoke-1",
      "type": "echo.result",
      "payload": {
        "text": "smoke"
      },
      "attachments": [
        {
          "id": "file-1",
          "name": "smoke.txt",
          "mimeType": "text/plain",
          "size": 12
        }
      ]
    },
    "files": {
      "file-1": {
        "name": "smoke.txt",
        "bytes": 12,
        "text": "smoke-binary"
      }
    }
  }
}
```

이 smoke는 브라우저 대신 Python `aiortc` master 클라이언트를 사용합니다. 따라서 브라우저 UI를 열지 않아도 서버, worker main, slave subprocess, signaling, DataChannel handler call과 binary attachment roundtrip까지 한 번에 검증할 수 있습니다.

## 11. 구현 중 오래 걸렸던 시행착오

이번 구현에서 시간이 오래 걸린 부분은 “코드가 틀렸다”기보다, 여러 런타임 경계가 동시에 얽힌 부분들이었습니다. 나중에 비슷한 문제를 만났을 때 바로 떠올릴 수 있도록 남깁니다.

### 11.1 Pydantic settings와 comma-separated list

처음에는 `GPSTATION_V1_CORS_ORIGINS`를 comma-separated string으로 두고 `cors_origins: list[str]` 필드에 validator를 붙였습니다. 그런데 `pydantic-settings`는 list 같은 complex field를 validator 전에 JSON으로 해석하려고 합니다.

그래서 이 값이 실패했습니다.

```text
GPSTATION_V1_CORS_ORIGINS=http://127.0.0.1:3001,http://localhost:3001
```

해결은 단순하게 했습니다.

- 설정 필드는 `cors_origins: str`
- 실제 FastAPI CORS middleware에 넘길 때 `cors_origin_list` property에서 split

관련 파일:

- `server/gpstation_server/settings.py`
- `server/gpstation_server/main.py`

### 11.2 PowerShell에서 background process를 띄울 때 PYTHONPATH quoting

처음에는 `Start-Process powershell -Command "$env:PYTHONPATH='...'; python ..."` 형태로 서버/워커를 띄웠습니다. 그런데 quoting이 깨지면서 PowerShell이 `=D:\...` 같은 문자열을 command로 해석했습니다.

결과적으로 서버가 뜨지 않았고 `.run/v1-server.err.log`에 인코딩이 깨진 오류가 남았습니다.

검증 때는 더 안전한 형태로 임시 우회했습니다.

```powershell
cmd.exe /c set PYTHONPATH=...&& python -m gpstation_server
```

현재 repo의 정상 실행 경로는 이 문제를 피하기 위해 Poetry를 사용합니다. `server/run.bat`와 `worker/run.bat`도 각각 `poetry run gpstation-v1-server`, `poetry run gpstation-v1-worker`를 호출합니다.

### 11.3 Next/Turbopack이 local scoped package를 못 찾은 문제

`example/web`은 `@gpstation/v1-master-js-sdk`를 `file:` dependency로 사용합니다. 처음에는 JS SDK가 `src/index.ts`를 직접 export했습니다.

TypeScript typecheck는 통과했지만 `next build`의 Turbopack production build가 scoped local package를 못 찾았습니다.

해결은 두 가지였습니다.

1. JS SDK를 `dist/`로 빌드하고 package export를 `dist/index.js`와 `dist/index.d.ts`로 변경
2. 예제 앱 production build를 `next build --webpack`으로 고정

관련 파일:

- `sdk/master/js/package.json`
- `sdk/master/js/tsconfig.build.json`
- `example/web/package.json`
- `example/web/next.config.mjs`

### 11.4 React 19 lint의 ref render access 규칙

처음에는 버튼 disabled 조건에서 `peerRef.current`를 직접 읽었습니다.

```tsx
disabled={busy || !peerRef.current}
```

React 19 lint는 render 중 ref access를 막습니다. ref는 render를 일으키지 않는 값이므로 UI 상태 판단에 직접 쓰면 화면이 예상대로 갱신되지 않을 수 있습니다.

해결은 `connected` state를 따로 두는 것이었습니다.

```tsx
const [connected, setConnected] = useState(false);
```

`peerRef`는 실제 객체 보관용, `connected`는 화면 렌더링용입니다.

### 11.5 Subprocess ready race

worker main은 subprocess가 `ready`라고 말할 때까지 기다립니다. 그런데 stdout reader가 종료될 때도 `ready_event`를 set하면, subprocess가 준비되기 전에 죽어도 main process가 잘못해서 `session.ready`를 서버에 보낼 수 있습니다.

이를 막기 위해 `ManagedSession`에 `ready` flag를 추가했습니다.

- `ready_event`: 기다리는 task를 깨우기 위한 이벤트
- `ready`: 실제 subprocess가 ready 메시지를 보냈는지 나타내는 상태

이 둘을 분리하면 “기다림을 끝내야 하는 상황”과 “진짜 준비 완료”를 구분할 수 있습니다.

관련 파일:

- `worker/gpstation_worker_v1/subprocess_manager.py`

### 11.6 WebRTC smoke에서 echo 응답을 받았는데 Future가 안 깨어난 문제

가장 시간이 오래 걸렸던 부분입니다.

E2E smoke는 다음 단계까지 성공했습니다.

1. session 생성 성공
2. signaling WebSocket 연결 성공
3. offer 전송
4. answer 수신
5. DataChannel open
6. slave subprocess가 `call.response` 전송
7. client callback도 DataChannel message 수신

그런데 smoke script의 `await result`가 끝나지 않았습니다.

원인은 `aiortc` callback에서 asyncio Future를 직접 `set_result()`하는 방식이 event loop wake-up과 맞지 않았기 때문입니다. callback이 어떤 실행 context에서 호출되는지 애매할 때는 loop에 thread-safe하게 결과 설정을 예약하는 것이 안전합니다.

수정 전 느낌:

```python
result.set_result(payload)
```

수정 후:

```python
loop.call_soon_threadsafe(result.set_result, payload)
```

관련 파일:

- `scripts/smoke_aiortc_e2e.py`

### 11.7 WebRTC 디버깅은 로그 위치가 중요하다

처음에는 slave subprocess가 DataChannel 메시지를 받는지 알 수 없었습니다. subprocess stderr는 worker main이 읽어서 stdout으로 넘깁니다. 그래서 다음 로그를 추가했습니다.

- subprocess가 DataChannel을 받았는지
- DataChannel message를 받았는지
- `call.response`를 보냈는지
- smoke client가 DataChannel message를 받았는지

이 로그 덕분에 “worker가 못 받는 문제”가 아니라 “client Future가 안 깨어나는 문제”라는 걸 좁힐 수 있었습니다.

관련 파일:

- `sdk/slave/python/gpstation_slave_sdk_v1/runtime.py`
- `worker/slave_plugins/echo/app.py`
- `worker/gpstation_worker_v1/subprocess_manager.py`
- `scripts/smoke_aiortc_e2e.py`

## 12. 자주 볼 에러와 확인 위치

서버가 안 뜨면:

```powershell
Get-Content -Encoding UTF8 .run\v1-server.err.log -Tail 80
```

worker가 서버에 안 붙으면:

```powershell
Get-Content -Encoding UTF8 .run\v1-worker.err.log -Tail 80
Get-Content -Encoding UTF8 .run\v1-worker.out.log -Tail 80
```

worker 목록이 비어 있으면:

- worker process가 실행 중인지 확인
- worker token이 `demo-worker-token`인지 확인
- server URL이 `http://127.0.0.1:8100`인지 확인

session 생성이 실패하면:

- 선택한 `worker_session_id`가 현재 사용자 소유인지 확인
- worker 상태가 `ready` 또는 `busy`인지 확인
- worker control WebSocket이 끊기지 않았는지 확인

DataChannel이 안 열리면:

- 브라우저 콘솔 로그 확인
- server signaling WebSocket 로그 확인
- slave subprocess stdout/stderr relay 로그 확인
- `scripts/smoke_aiortc_e2e.py`로 브라우저 없이 먼저 검증

## 13. 다음 단계로 확장하려면

이 MVP 다음에 가장 자연스러운 확장 순서는 다음과 같습니다.

1. echo 외의 실제 slave app plugin 추가
2. Python master SDK에 WebRTC client 기능 추가
3. in-memory state를 DB 또는 Redis로 이동
4. static token map을 기존 사용자/auth 시스템과 연결
5. worker capacity와 multi-session 정책 정의
6. timeout, cancel, progress, result 메시지를 DataChannel protocol에 추가
7. master 예제에서 request/response history와 binary payload 테스트 추가

## 14. 한 줄 요약

`app_v1/` MVP는 “master가 사용자의 worker와 slave app을 명시 선택하고, 서버는 세션과 signaling만 조율하며, 실제 작업 메시지는 WebRTC DataChannel로 master와 slave subprocess가 직접 주고받는다”는 구조를 최소 기능으로 증명합니다.
