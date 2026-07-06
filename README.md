GP Station (gps.qutat.com)

<제공 가치>
- 고성능 컴퓨터를 Worker 로 돌려놓고, 컴퓨팅 자원이 부족한 환경(모바일, 노트북, 웹서버 등)에서 API 처럼 사용한다.
- 대상 : 로컬 AI 모델(LLM, SDXL 등) 사용을 위해 VRAM 24 GB 이상급 컴퓨팅 파워를 보유하고 있는 리테일 사용자들.


<작업 흐름>
1. 사용자/API가 GP Station에 session 생성 요청
2. GP Station이 Worker 메인 앱에 session_start 명령 전송
3. Worker 메인 앱이 worker subprocess 실행
4. subprocess가 WebRTC PeerConnection 준비
5. subprocess가 메인 앱에 signaling endpoint 준비 완료 보고
6. 메인 앱이 GP Station에 session_ready 보고
7. 사용자/API가 GP Station에서 session_id와 short-lived token을 받음
8. 사용자/API가 GP Station signaling API/WebSocket에 접속
9. 사용자/API와 subprocess가 GP Station을 통해 SDP/ICE 교환
10. WebRTC DataChannel 체결
11. 이후 사용자/API ⇄ worker subprocess 직접 통신
12. 작업 종료 또는 timeout 시 subprocess 종료


<구조도>

[Worker Main App]
      │
      │ WebSocket control
      ▼
[GP Station Server]
      ▲
      │ signaling API/WebSocket
      │
[Client / Backend / Browser]

연결 체결 후:

[Client / Backend / Browser]
      ⇄ WebRTC DataChannel ⇄
[Worker Subprocess]


<프로세스 별 동작>

Worker Main App
- GP Station과 WebSocket control channel 유지
- session_start 수신
- worker subprocess 생성
- subprocess와 local IPC 연결
- signaling 메시지 proxy
- subprocess lifecycle 관리

Worker Subprocess
- WebRTC PeerConnection 담당
- DataChannel 담당
- job protocol 처리
- 직접 client/backend/browser와 통신
- close/cancel/progress/result 처리

GP Station
- session 생성
- 권한 검증
- session descriptor 제공
- signaling relay
- session metadata 저장
- TTL/상태/쿼터 관리

Client/Backend/Browser
- session descriptor 조회
- WebRTC offer 생성
- signaling 수행
- DataChannel로 subprocess 직접 제어


<Server DB>
- Users
- AccessKey
- Workers
- Masters
- Slaves
