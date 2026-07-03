컨텍스트 플레이 페이지

<라우팅>
- context-play/:example_id


<접근 권한>
- admin, user, guest

<구성 요소>
- 헤더 겸 제어 패널
- 이미지
- WordHighlighter
- kr_text
- 선택지 목록

<상세>
- 헤더에서 "다른 예문" 버튼을 누르면 무작위로 다른 example_id 페이지로 이동
- /example/context-play API 를 통해 필요한 데이터들을 한 번에 가져와서 띄운다.
- 오디오는 로드시 무작위로 하나 재생 + 이미지를 누르면 무작위로 다시 선택해서 다시 재생
(이때, 눌렀을 때 오디오를 가져오는 게 아니라 페이지를 로드했을 때 다 가져온 후 누르면 재생만)
- jp_words 로 WordHighlighter 표시
- example.kr_text 는 처음에는 숨기고, 클릭하여 잠시 펼칠 수 있음 (다른 example 페이지로 이동 시에는 다시 접음)
- 선택지 목록은 similar_examples 의 jp_text 들만 객관식 문항처럼 나열하고, 클릭하면 해당 example 페이지로 이동한다.




<전용 최적화 백엔드 API (public)>
(Input)
- example_id, skills
(Output)
- ExampleBase
- /image/closest-by-example 과 같은 알고리즘으로 example_id 에 대해 뽑은 이미지 파일의 url 값
- Example.audios 들의 오디오 파일의 url 값 목록
- Example.jp_text 및 skills(guest 인 경우) analyze_jp_text 로 보내서 받은 결과
- Example.text_embedding 과 context_embedding 이 가장 유사한 상위 5개 Example들의 ExampleBase




