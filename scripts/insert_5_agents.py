from databricks.sdk import WorkspaceClient
from codex_agentops.config import load_settings

settings = load_settings()
w = WorkspaceClient(profile=settings.profile)
wh_id = settings.warehouse_id

agents_data = [
    ("test-skill-agent", "Test Skill Agent", "텍스트 지표 분석 및 검증 에이전트", "skill-based-agent", "ino0121@saltware.co.kr", "AI-CoE", "중", "내부", "{}", "production", "1.0.0", "", "1.0.0", "skill", "apps", "databricks", "일반", "[]", False, "databricks-meta-llama-3-3-70b-instruct"),
    ("financial-calculator-agent", "Financial Calculator Agent", "공급가액 및 부가세 세무 감사 에이전트", "skill-based-agent", "alice@saltware.co.kr", "Finance-Tech", "상", "내부", "{}", "production", "1.0.0", "", "1.0.0", "skill", "apps", "databricks", "일반", "[]", False, "databricks-meta-llama-3-3-70b-instruct"),
    ("doc-summary-agent", "Document Summary Agent", "주요 키워드 빈도 추출 및 요약 평가 에이전트", "skill-based-agent", "charlie@saltware.co.kr", "Data-Platform", "중", "공개", "{}", "production", "1.0.0", "", "1.0.0", "skill", "apps", "databricks", "일반", "[]", False, "databricks-meta-llama-3-3-70b-instruct"),
    ("customer-faq-agent", "Customer FAQ Agent", "고객 FAQ 검색 및 감정 분석 에이전트", "skill-based-agent", "bob@saltware.co.kr", "Customer-Success", "하", "공개", "{}", "staging", "1.0.0", "", "1.0.0", "skill", "apps", "databricks", "일반", "[]", False, "databricks-meta-llama-3-3-70b-instruct"),
    ("code-review-agent", "Code Review Agent", "코드 보안 및 스타일 검사 에이전트", "agent-bricks-agent", "david@saltware.co.kr", "DevOps", "중", "내부", "{}", "draft", "0.1.0", "", "0.1.0", "code", "apps", "databricks", "일반", "[]", False, "databricks-meta-llama-3-3-70b-instruct")
]

values = []
for d in agents_data:
    v = f"""(
        '{d[0]}', '{d[1]}', '{d[2]}', '{d[3]}', '{d[4]}', '{d[5]}',
        '{d[6]}', '{d[7]}', '{d[8]}', '{d[9]}', '{d[10]}', '{d[11]}',
        current_timestamp(), current_timestamp(),
        '{d[12]}', '{d[13]}', '{d[14]}', '{d[15]}', '{d[16]}',
        from_json('{d[17]}', 'array<struct<object:string,privilege:string>>'),
        {str(d[18]).lower()}, '{d[19]}'
    )"""
    values.append(v)

sql = f"""
INSERT INTO sk_inno_aops.agentops_test.agents (
    agent_id, name, description, agent_type, owner, owner_group,
    service_criticality, data_sensitivity, success_criteria_json, lifecycle,
    current_version, spec_uri, created_at, updated_at,
    agent_version, build_type, serving_type, origin, security_level,
    uc_permissions, flagship_model, model_service
) VALUES {', '.join(values)}
"""
res = w.statement_execution.execute_statement(warehouse_id=wh_id, statement=sql, wait_timeout="30s")
print("Insert status:", res.status.state)
if res.status.error:
    print("Error:", res.status.error)

check = w.statement_execution.execute_statement(warehouse_id=wh_id, statement="SELECT agent_id, name, lifecycle FROM sk_inno_aops.agentops_test.agents", wait_timeout="30s")
print("Agents in table:")
if check.result and check.result.data_array:
    for r in check.result.data_array:
        print(" ", r)

