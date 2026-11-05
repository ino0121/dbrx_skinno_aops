import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from databricks.sdk import WorkspaceClient

w = WorkspaceClient(profile="dbx_ino0121_saltware")
warehouse_id = "c4ff4cc877b27739"

# 1. Update agents with normalized agent_type ('Skill-based', 'Code-based', 'No-code')
sql_update_agents = """
UPDATE sk_inno_aops.agentops_test.agents
SET agent_type = CASE
    WHEN agent_id = 'test-skill-agent' THEN 'Skill-based'
    WHEN agent_id = 'doc-summary-agent' THEN 'Skill-based'
    WHEN agent_id = 'financial-calculator-agent' THEN 'Code-based'
    WHEN agent_id = 'customer-faq-agent' THEN 'No-code'
    WHEN agent_id = 'code-review-agent' THEN 'Code-based'
    ELSE 'Skill-based'
END
"""

# 2. Reset and sync agent_production with exact 3 approved deployed agents
sql_clear_production = "DELETE FROM sk_inno_aops.agentops_test.agent_production"
sql_insert_production = """
INSERT INTO sk_inno_aops.agentops_test.agent_production
(agent_id, target_version, promoted_by, promoted_at, promotion_reason)
VALUES
('test-skill-agent', '1.0.0', 'ino0121@saltware.co.kr', current_timestamp(), 'Production GA Promotion Approved'),
('doc-summary-agent', '1.0.0', 'charlie@saltware.co.kr', current_timestamp(), 'Enterprise Document Intelligence Released'),
('financial-calculator-agent', '1.0.0', 'alice@saltware.co.kr', current_timestamp(), 'Financial Audit Service Live')
"""

# 3. Align release_gates to match deployed agents: exactly 3 approved, others pending/rejected
sql_clear_gates = "DELETE FROM sk_inno_aops.agentops_test.release_gates"
sql_insert_gates = """
INSERT INTO sk_inno_aops.agentops_test.release_gates
(gate_id, agent_id, version, checks_json, decision, evidence_ref, decided_by, decided_at, upgrade_type)
VALUES
('gate_001', 'test-skill-agent', '1.0.0', '{\"accuracy\": 0.95, \"security\": \"pass\"}', 'approved', 'dbfs:/audit/test-skill-agent-v1.json', 'lead-architect@saltware.co.kr', current_timestamp(), 'minor'),
('gate_002', 'doc-summary-agent', '1.0.0', '{\"accuracy\": 0.94, \"security\": \"pass\"}', 'approved', 'dbfs:/audit/doc-summary-v1.json', 'lead-architect@saltware.co.kr', current_timestamp(), 'minor'),
('gate_003', 'financial-calculator-agent', '1.0.0', '{\"accuracy\": 0.98, \"security\": \"pass\"}', 'approved', 'dbfs:/audit/fin-calc-v1.json', 'compliance-officer@saltware.co.kr', current_timestamp(), 'major'),
('gate_004', 'customer-faq-agent', '1.0.0', '{\"accuracy\": 0.82, \"security\": \"review_required\"}', 'pending', 'dbfs:/audit/faq-agent-v1.json', 'lead-architect@saltware.co.kr', current_timestamp(), 'minor'),
('gate_005', 'code-review-agent', '0.1.0', '{\"security\": \"audit_pending\"}', 'pending', 'dbfs:/audit/code-review-v0.1.json', 'devops-lead@saltware.co.kr', current_timestamp(), 'patch')
"""

for desc, sql in [
    ("Update agents agent_type", sql_update_agents),
    ("Clear agent_production", sql_clear_production),
    ("Insert agent_production (3 deployed)", sql_insert_production),
    ("Clear release_gates", sql_clear_gates),
    ("Insert release_gates (3 approved, 2 pending)", sql_insert_gates)
]:
    res = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=sql,
        wait_timeout="30s"
    )
    print(f"[{desc}]: {res.status.state}")
    if res.status.error:
        print(f"  Error: {res.status.error.message}")

