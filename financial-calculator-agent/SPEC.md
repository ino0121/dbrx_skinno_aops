---
agent_id: financial-calculator-agent
agent_name: Financial Calculator Agent
agent_version: "1.0.0"
build_type: skill
serving_type: apps
origin: databricks
owner: alice@saltware.co.kr
owner_group: Finance-Tech
service_criticality: 상
data_sensitivity: 내부
security_level: 일반
uc_permissions: []
success_criteria:
  correctness_min: 0.95
  relevance_min: 0.9
  safety_min: 1.0
  latency_p90_seconds: 5
flagship_model: false
model_service: databricks-meta-llama-3-3-70b-instruct
---

# Financial Calculator Agent 설계서 (SPEC)

## 1. 해결하려는 문제
거래 금액에 대한 부가세, 공급가액, 원천징수액을 도구로 계산하고 세무 서브에이전트를 통해 검증합니다.

## 2. 사용자와 사용 시나리오
재무 담당자가 거래명세서 금액의 세무 산출 내역을 검증할 때 사용합니다.

## 3. 사용하는 데이터와 도구
- Tool: `vat_calculator` (공급가액 및 부가세 10% 자동 계산)
- Subagent: `tax_auditor` (산출된 세액의 법적/수치 정합성 검토)

## 4. 성공 기준과 평가 방법
- 도구 계산 결과가 수치적으로 정확해야 합니다.
- 서브에이전트가 감사 의견을 명확히 제시해야 합니다.

## 5. 제약 사항과 가드레일
기밀 재무 원장을 외부에 누출하지 않습니다.
