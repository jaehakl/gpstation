Example 편집기

# UI

<문장 패널>
- text input : 기준 일본어 문장 입력
- text input : 일본어 단어 입력
- text input : 일본어 문장 생성/수정 (10 단어 이하로 제한)
- text input : 한국어 뜻 생성/수정
-> 문장 단위로 한 번에 저장

<단어 생성>
- word highlighter : 일본어 문장에서 형태소 추출하여 표시
- word input modal : 추출된 형태소별 발음, 뜻 생성/수정
-> 단어 별 저장

<오디오 생성>
- 성우, 톤 입력 (무작위 reroll 가능) 후 생성 (백엔드에서 진행)
- card grid : 생성된 오디오 목록 표시(재생, 삭제 가능)

<이미지 선택/생성>
- 이미지 검색 모달 : 기존 이미지 검색하여 연결 (embedding 가까운 순으로 정렬하여 표시, 시멘틱 검색 가능)
- text input : SDXL positive/negative prompt 생성
- img src : 현재 선택된 이미지 표시
- tile grid : 현재 연결된 이미지 목록 표시(상세보기 팝업, unlink, 삭제 가능)

# 백엔드
- 