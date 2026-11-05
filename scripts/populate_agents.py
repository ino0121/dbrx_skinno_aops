from databricks.sdk import WorkspaceClient
from codex_agentops.config import load_settings

settings = load_settings()
w = WorkspaceClient(profile=settings.profile)
wh_id = settings.warehouse_id

sql = """
INSERT INTO sk_inno_aops.agentops_test.agents (
    agent_id, name, description, agent_type, agent_version, build_type, serving_type,
    origin, owner, owner_group, service_criticality, data_sensitivity, security_level,
    flagship_model, model_service, lifecycle, current_version, created_at, updated_at
) VALUES 
(
    'test-skill-agent', 'Test Skill Agent', '텍스트 지표 분석 및 검증용 Skill 에이전트',
    'skill-based-agent', '1.0.0', 'skill', 'apps', 'databricks',
    'ino0121@saltware.co.kr', 'AI-CoE', '중', '내부', '일반',
    false, 'databricks-meta-llama-3-3-70b-instruct', 'production', '1.0.0', current_timestamp(), current_timestamp()
),
(
    'financial-calculator-agent', 'Financial Calculator Agent', '공급가액 및 부가세 계산 세무 감사 에이전트',
    'skill-based-agent', '1.0.0', 'skill', 'apps', 'databricks',
    'alice@saltware.co.kr', 'Finance-Tech', '상', '내부', '일반',
    false, 'databricks-meta-llama-3-3-70b-instruct', 'production', '1.0.0', current_timestamp(), current_timestamp()
),
(
    'doc-summary-agent', 'Document Summary Agent', '주요 키워드 빈도 추출 및 요약 평가 에이전트',
    'skill-based-agent', '1.0.0', 'skill', 'apps', 'databricks',
    'charlie@saltware.co.kr', 'Data-Platform', '중', '공개', '일반',
    false, 'databricks-meta-llama-3-3-70b-instruct', 'production', '1.0.0', current_timestamp(), current_timestamp()
)
"""
w.statement_execution.execute_statement(warehouse_id=wh_id, statement=sql, wait_timeout="30s")
print("agents table populated with 3 active agents!")

