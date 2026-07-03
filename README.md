GP Station (gps.qutat.com)

<제공 가치>
- 컴퓨팅 자원 풀링 시스템
- 컴퓨팅 자원을 사용하지 않을 때 다른 사람의 작업을 처리하도록 하여 크레딧을 쌓고, 쌓을 크레딧으로 필요할 때 다른 사람의 컴퓨팅 자원을 이용한다.
- 컴퓨팅 자원이 부족한 환경(모바일, 노트북, 웹서버 등)에서도 고성능 컴퓨팅 자원이 요구되는 작업을 처리할 수 있다.
- 대상 : 로컬 AI 모델(LLM, SDXL 등) 사용을 위해 VRAM 24 GB 이상급 컴퓨팅 파워를 보유하고 있는 리테일 사용자들.

<아키텍처>
(1) 플랫폼서버
- 로그인 된 클라이언트들 및 작업 현황, 이용률 등을 모니터링한다.
- 간단한 챗봇이나 이미지 생성 같은 건 여기에서 바로 할 수 있다.
- 컴퓨팅 공급자 용 API 와 사용자 용 API 를 각각 제공한다.
- 사용자는 API 를 통해 쿼리를 업로드할 수 있고, 이를 통해 자신이 자체 개발한 앱에 통합하여 활용할 수도 있다.

(2) 클라이언트
- 인증된 계정으로 로그인한다.
- 플랫폼 서버 API로부터 새로운 매칭되는 작업이 있으면 가져온다.
- 작업을 수행하고 결과를 플랫폼 서버 API 로 리턴한다.
- 작업 수행 / 중지 제어
- 작업 내역, 크레딧 획득량 등 모니터링
- GPU 스펙 및 상태(온도, 메모리 점유율 등) 로그 모니터링
- 모델 설치, 연결, 관리

<검토 사항>
- 로그를 철저하게 남기는 게 중요하다. (보안, 프라이버시 분쟁 발생 및 보상 크레딧 책정 관련 등)
- 보안, 프라이버시, 신뢰도 차원에서 작업자의 신용도 관리가 필요하며, 신용도에 따른 크레딧 차등 지급, 작업 요청자에게 신용도에 따른 필터링, 화이트리스트 등 기능 필요
- 작업자 별 VRAM, 보유 모델 등에 따른 구분이 필요하다.
- Race condition 은 어떻게 방지할 수 있을까?
- 데이터 삭제는 어떤 기준으로 하는 게 좋을까?
- 모든 작업 PC들이 자동으로 무조건 1초 마다 eventloop 처럼 api 에 새 요청이 있는지 fetch 시키면 서버에 부담이 되지는 않을까? (게다가 사용자도 작업이 완료되었는지 여부를 eventloop 로 새로고침해야할것이다.)
- 미완성된 결과물을 돌려줬는지 어떻게 검증하는가? (예를 들어 31B 모델로 계산할 것을 주문했는데 3B 모델로 바꿔치기하여 싸게 돌린 결과를 돌려주면서 크레딧만 빨아간다거나)



### DB
    
* User
    - id
    - email
    - username
    - display_name
    - password_hash
    - role
    - status
    - credit_balance
    - credit_pending
    - credit_withdrawable
    - trust_score
    - trust_tier
    - success_job_count
    - failed_job_count
    - disputed_job_count
    - created_at
    - updated_at
    - last_login_at
    - metadata_json

* WorkerSession
    - id
    - user_id
    - status
    - accepting_jobs
    - session_token_hash
    - ip_address
    - user_agent
    - client_version
    - gpu_name
    - gpu_vendor
    - vram_total_mb
    - vram_available_mb
    - gpu_utilization_pct
    - gpu_temperature_c
    - supported_task_types
    - installed_model_ids
    - current_job_id
    - connected_at
    - last_heartbeat_at
    - disconnected_at
    - expires_at
    - created_at
    - updated_at
    - metadata_json

* AccessKey
    - id
    - user_id
    - key_type              -- api / worker
    - name
    - key_prefix            -- gps_api_abcd / gps_worker_efgh
    - key_hash              -- 원본 key 저장 금지
    - scopes                -- json array
    - status                -- active / revoked / expired
    - rate_limit_per_minute
    - allowed_ips           -- optional
    - allowed_origins       -- optional
    - last_used_at
    - expires_at
    - created_at
    - revoked_at
    - metadata_json

* Job
    - id
    - requester_user_id
    - worker_user_id
    - worker_session_id
    - task_type
    - status
    - priority
    - required_model_id
    - required_vram_gb
    - required_trust_tier
    - verification_policy
    - price_limit_credit
    - estimated_cost_credit
    - final_cost_credit
    - worker_reward_credit
    - platform_fee_credit
    - lease_expires_at
    - retry_count
    - max_retries
    - started_at
    - completed_at
    - failed_at
    - cancelled_at
    - error_code
    - error_message
    - created_at
    - updated_at
    - metadata_json

* JobMessage
    - id
    - job_id
    - kind
    - role
    - status
    - parent_message_id
    - created_by_user_id
    - created_at
    - metadata_json

* StoredObject
    - id
    - object_type
    - storage_backend
    - uri
    - inline_content
    - mime_type
    - size_bytes
    - sha256
    - created_by_user_id
    - expires_at
    - created_at
    - metadata_json

* JobMessagePart
    - id
    - message_id
    - object_id
    - name
    - part_type
    - sort_order
    - required
    - created_at
    - metadata_json

* JobEvent
    - id
    - job_id
    - event_type
    - actor_user_id
    - actor_role
    - from_status
    - to_status
    - message_id
    - object_id
    - error_code
    - error_message
    - request_id
    - trace_id
    - created_at
    - metadata_json

* CreditLedger
    - id
    - user_id
    - job_id
    - counterparty_user_id
    - type
    - amount
    - balance_type
    - status
    - related_ledger_id
    - idempotency_key
    - reason
    - created_at
    - settled_at
    - metadata_json