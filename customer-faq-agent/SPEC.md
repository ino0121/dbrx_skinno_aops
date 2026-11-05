---
agent_id: customer-faq-agent
agent_name: Customer FAQ Agent
agent_version: "1.0.0"
build_type: skill
serving_type: apps
origin: databricks
owner: bob@saltware.co.kr
owner_group: Customer-Success
service_criticality: 하
data_sensitivity: 공개
security_level: 일반
uc_permissions: []
success_criteria:
  correctness_min: 0.9
  relevance_min: 0.95
  safety_min: 1.0
  latency_p90_seconds: 5
flagship_model: false
model_service: databricks-meta-llama-3-3-70b-instruct
---

# Customer FAQ Agent 설계서 (SPEC)

## 1. 해결하려는 문제
고객 문의에 대해 사전 등록된 FAQ 데이터베이스를 검색하고, 서브에이전트를 통해 감정 및 긴급도를 분류합니다.

## 2. 사용자와 사용 시나리오
고객지원팀 담당자가 접수된 문의의 표준 답변을 조회하고 티켓 우선순위를 판별할 때 사용합니다.

## 3. 사용하는 데이터와 도구
- Tool: `faq_matcher` (고객 문의 키워드 매칭 FAQ 답변 검색)
- Subagent: `sentiment-analyst` (문의 고객의 감정 및 긴급도 분석)

## 4. 성공 기준과 평가 방법
- FAQ 답변 매칭이 정확해야 합니다.
- 감정 분석 결과가 합리적으로 제시되어야 합니다.

## 5. 제약 사항과 가드레일
개인 식별 정보(전화번호, 주민등록번호 등)를 응답에 포함하지 않습니다.

