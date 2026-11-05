# Document Summary Agent

## 실행 순서

1. `keyword-extractor` Skill을 통해 `keyword_extractor` 도구를 실행하여 문서의 주요 키워드를 추출합니다.
2. `summary-reviewer` Subagent를 호출하여 추출된 키워드를 바탕으로 문서 요약의 완결성을 검증합니다.
3. 검증된 최종 요약 보고서를 취합하여 응답합니다.

