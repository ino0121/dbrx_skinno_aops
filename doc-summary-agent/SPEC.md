---
agent_id: doc-summary-agent
agent_name: Document Summary Agent
agent_version: "1.0.0"
build_type: skill
serving_type: apps
origin: databricks
owner: charlie@saltware.co.kr
owner_group: Data-Platform
service_criticality: 중
data_sensitivity: 공개
security_level: 일반
uc_permissions: []
success_criteria:
  correctness_min: 0.85
  relevance_min: 0.9
  safety_min: 1.0
  latency_p90_seconds: 8
flagship_model: false
model_service: databricks-meta-llama-3-3-70b-instruct
---

# Document Summary Agent 설계서 (SPEC)

## 1. 해결하려는 문제
문서의 핵심 단어와 빈도를 추출하고, 서브에이전트를 통해 주제 요약의 타당성을 검증합니다.

## 2. 사용자와 사용 시나리오
데이터 엔지니어 및 분석가가 기술 문서를 빠르게 브리핑할 때 사용합니다.

## 3. 사용하는 데이터와 도구
- Tool: `keyword_extractor` (주요 키워드 출현 빈도 추출)
- Subagent: `summary-reviewer` (추출된 키워드 기반의 요약 완결성 평가)

## 4. 성공 기준과 평가 방법
- 키워드 빈도 산출이 정확해야 합니다.
- 서브에이전트가 완결성 평가를 제공해야 합니다.

## 5. 제약 사항과 가드레일
원문에 없는 가짜 사실(환각)을 생성하지 않습니다.

