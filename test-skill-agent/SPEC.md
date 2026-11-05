---
agent_id: test-skill-agent
agent_name: Test Skill Agent
agent_version: "1.0.0"
build_type: skill
serving_type: apps
origin: databricks
owner: ino0121@saltware.co.kr
owner_group: AI-CoE
service_criticality: 하
data_sensitivity: 내부
security_level: 일반
uc_permissions: []
success_criteria:
  correctness_min: 0.8
  relevance_min: 0.9
  safety_min: 1.0
  latency_p90_seconds: 10
flagship_model: false
model_service: databricks-meta-llama-3-3-70b-instruct
---

# Test Skill Agent 설계서 (SPEC)

## 1. 해결하려는 문제
문서 텍스트의 정량적 지표를 도구로 산출하고, 서브에이전트를 통해 검증한 뒤 최종 결과를 요약합니다.

## 2. 사용자와 사용 시나리오
관제 및 메트릭 파이프라인의 텔레메트리(Subagent, Tool, Token, Latency) 수집 가능 여부를 테스트합니다.

## 3. 사용하는 데이터와 도구
- Tool: `text_metrics_calculator` (단어 수, 문자 수, 문장 수 분석 도구)
- Subagent: `verifier` (분석 결과 정합성 검증 서브에이전트)

## 4. 성공 기준과 평가 방법
- 도구 실행이 정상 완료되어야 합니다.
- 서브에이전트가 검증 결과를 반환해야 합니다.

## 5. 제약 사항과 가드레일
기밀 정보나 인증 토큰을 출력하지 않습니다.

