# GPStation Platform UI

Next.js 기반 플랫폼 계정/관리 콘솔입니다.

- Google OAuth + cookie JWT 인증 흐름을 사용합니다.
- `src/api/api.ts`의 `dbTables`가 플랫폼 테이블 메타데이터와 현재 사용 가능한 API 엔드포인트를 관리합니다.
- 현재 화면은 계정 정보, 관리자 사용자 목록, 플랫폼 테이블 스키마 카탈로그를 제공합니다.
