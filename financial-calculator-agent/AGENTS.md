# Financial Calculator Agent

## 실행 순서

1. `vat-calculator` Skill을 통해 `vat_calculator` 도구를 실행하여 입력 금액의 공급가액과 부가세를 산출합니다.
2. `tax_auditor` Subagent를 호출하여 계산된 세액 내역의 정합성을 검증합니다.
3. 최종 감사 확인 결과를 취합하여 응답합니다.

