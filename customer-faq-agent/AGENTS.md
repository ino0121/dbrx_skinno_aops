# Customer FAQ Agent

## 실행 순서

1. `faq-matcher` Skill을 통해 `faq_matcher` 도구를 실행하여 입력 질의에 해당하는 FAQ 답변을 검색합니다.
2. `sentiment-analyst` Subagent를 호출하여 고객 문의의 감정 상태(긍정/부정/중립)와 긴급도를 판정합니다.
3. 표준 답변과 감정 분석 결과를 취합하여 최종 응답을 작성합니다.

