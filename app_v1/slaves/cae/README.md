# CAE slave

Caemble의 fully-built `BuiltSample`과 `BuiltSetup`만 받아 Python kernel을 실행하고, 선언된
RecordedData만 GPStation WebRTC result attachment로 반환한다. GPStation SDK 소스는 수정하지
않으며 application-level `cae.simulation.start` → `cae.simulation.next` protocol을 사용한다.

```powershell
cd app_v1/slaves/cae
poetry install
poetry run pytest
```

Windows에서는 repository root의 `install_app_v1_slave_cae.bat`을 사용할 수 있다.
`poetry.toml`은 AI slave와 동일하게 project-local `.venv`를 사용한다. Linux launcher
컴퓨터에서는 설치 후 다음 명령으로 실제 launcher가 사용할 환경을 검증한다.

```bash
cd /home/cavenet/gpstation/app_v1/slaves/cae
poetry install
test -x .venv/bin/python
poetry run python -c "import app, numpy, aiortc"
```

`poetry env info --path`가 이 폴더의 `.venv`가 아닌 기존 cache 환경을 가리키면
`poetry env remove --all`로 해당 프로젝트 환경을 제거한 후 `poetry install`을 다시
실행한다. `lr_launcher_run.sh`로 launcher를 실행한 경우 로그는 다음과 같이 확인한다.

```bash
tail -f /home/cavenet/gpstation/app_v1/launcher/launcher.log
```

Launcher는 `manifest.json`을 자동 검색한다. 첫 `next`가 계산을 시작하며 각 record는 다음
`next`의 `ackSequence`를 받아야 해제된다. 기본 실행 제한은 2시간, 첫 `next` 제한은 30초,
record ACK 제한은 120초다.

취소 시 CAE는 run의 pending tensor와 detached task를 정리한 뒤 launcher 내부용
`cae.run.cleaned` 확인을 보낸다. record 응답과 다음 `next` 사이처럼 cooperative cleanup을
확인할 수 없는 구간에서는 launcher가 2초 뒤 worker reset으로 승격하고, 기존 3초 종료 grace
이후에도 남은 프로세스는 재기동한다. 이 제어 메시지는 GPStation server로 전달하지 않는다.

`simulate.py`는 정확한 async ABI와 AST allowlist로 검증하며 import, 파일·네트워크 접근,
`eval` 및 임의 객체 호출을 허용하지 않는다. 이 정책은 신뢰된 Experiment source를 위한
가드레일이며 OS sandbox가 아니다. 운영 환경에서는 CAE worker 자체를 별도 OS 계정 또는
container 경계 안에서 실행해야 한다.
