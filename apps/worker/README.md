# GP Station Worker Client

GP Station Worker Client는 사용자의 로컬 PC에서 실행되는 터미널 프로그램이다. 플랫폼 API 서버와 WebSocket 연결을 유지하고, 로컬 GPU 상태를 서버에 보고한다.

현재 구현 범위는 WebSocket 통신 검증용 smoke MVP다. 작업 수신, runner subprocess 실행, 결과 업로드는 후속 단계에서 구현한다.

## Smoke MVP 목표

```text
1. AccessKey로 플랫폼 서버 WebSocket에 인증 연결한다.
2. 서버가 현재 인증된 user 정보와 worker session id를 반환한다.
3. worker CLI가 현재 로그인된 user 정보를 터미널에 출력한다.
4. worker CLI가 GPU 상태를 주기적으로 서버에 보낸다.
5. 플랫폼 UI 홈 화면에서 최근 worker GPU 상태를 표시한다.
```

## 실행

개발 환경에서는 `apps/worker`에서 실행한다.

```powershell
$env:GPSTATION_API_URL='http://localhost:8000'
$env:GPSTATION_ACCESS_KEY='gpsk_...'
poetry run gp-worker run
```

패키지 모듈 실행도 지원한다.

```powershell
poetry run python -m gpstation_worker
```

GPU 탐지만 확인하려면 다음을 실행한다.

```powershell
poetry run gp-worker gpu-info
```

설정 로딩 상태는 다음으로 확인한다. AccessKey 원문은 출력하지 않는다.

```powershell
poetry run gp-worker config-check
```

## 설정

MVP에서는 환경변수를 우선 사용한다.

```text
GPSTATION_API_URL=http://localhost:8000
GPSTATION_ACCESS_KEY=gpsk_...
GPSTATION_WORKER_NAME=home-4090
GPSTATION_GPU_INTERVAL_SEC=5
```

`GPSTATION_API_URL`은 자동으로 WebSocket URL로 변환된다.

```text
http://localhost:8000 -> ws://localhost:8000/app/v1/workers/ws
https://gps.qutat.com -> wss://gps.qutat.com/app/v1/workers/ws
```

## 인증

Worker WebSocket 인증은 플랫폼 AccessKey를 그대로 사용한다.

```text
Authorization: Bearer gpsk_...
```

기존 초안의 `X-GPS-Access-Key`, `X-GPS-Signature`, HMAC secret key 방식은 현재 AccessKey 시스템과 맞지 않으므로 MVP에서는 사용하지 않는다.

## WebSocket Protocol

연결 직후 worker는 `hello`를 보낸다.

```json
{
  "type": "hello",
  "device_name": "home-4090",
  "client_version": "0.1.0",
  "accepting_jobs": false
}
```

서버는 인증된 사용자와 세션 정보를 반환한다.

```json
{
  "type": "server_hello",
  "session_id": "...",
  "server_time": "...",
  "user": {
    "id": "...",
    "email": "...",
    "display_name": "...",
    "role": "user"
  }
}
```

이후 worker는 주기적으로 GPU 상태를 보낸다.

```json
{
  "type": "gpu_status",
  "status": "ready",
  "gpu": {
    "name": "NVIDIA GeForce RTX 4090",
    "vendor": "nvidia",
    "vram_total_mb": 24564,
    "vram_available_mb": 18320,
    "temperature_c": 58,
    "utilization_pct": 12
  }
}
```

GPU 수집은 `pynvml`을 우선 사용하고, 실패하면 `nvidia-smi`를 시도한다. 둘 다 실패하면 GPU 없음 상태를 전송한다.

## 현재 구조

```text
apps/worker/
├─ pyproject.toml
├─ README.md
└─ gpstation_worker/
   ├─ __init__.py
   ├─ __main__.py
   ├─ cli.py
   ├─ config.py
   ├─ gpu.py
   ├─ protocol.py
   └─ ws_client.py
```

## 후속 개발 단계

```text
Phase 1: WebSocket smoke MVP
- AccessKey 인증 연결
- server_hello 수신
- user 정보 터미널 출력
- GPU 상태 주기 보고
- 플랫폼 UI에서 worker session 표시

Phase 2: 작업 수신 준비
- worker 상태 머신
- job_offer 수신
- claim_job 전송
- lease_granted 수신

Phase 3: Runner 실행
- 작업별 임시 디렉터리 생성
- 입력 다운로드
- runner subprocess 실행
- progress 수집
- cancel 처리

Phase 4: 결과 제출
- 결과 파일 확인
- artifact hash 계산
- 결과 업로드
- job_completed, job_failed, job_cancelled 전송

Phase 5: 안정화
- 재연결 테스트
- Ctrl+C 종료 테스트
- subprocess kill 테스트
- GPU 온도 제한 테스트
- 로그 정리
```

## 검증

```powershell
cd apps/platform/api
poetry run python -m compileall app

cd apps/platform/ui
npm run typecheck
npm run lint

cd apps/worker
poetry install
poetry run python -m compileall gpstation_worker
poetry run gp-worker gpu-info
```
