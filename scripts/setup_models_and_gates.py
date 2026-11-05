import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from databricks.sdk import WorkspaceClient

w = WorkspaceClient(profile="dbx_ino0121_saltware")
warehouse_id = "c4ff4cc877b27739"

# 1. Update rate_cards with GPT and Claude models
sql_rate_cards = """
MERGE INTO sk_inno_aops.agentops_test.rate_cards t
USING (
    SELECT 'databricks-gpt-5-mini' AS model_service, 0.15 AS input_price_per_1m, 0.60 AS output_price_per_1m, 0.075 AS cache_read_price_per_1m
    UNION ALL
    SELECT 'databricks-claude-sonnet-4-5' AS model_service, 3.00 AS input_price_per_1m, 15.00 AS output_price_per_1m, 0.75 AS cache_read_price_per_1m
) s
ON t.model_service = s.model_service
WHEN MATCHED THEN UPDATE SET
    t.input_price_per_1m = s.input_price_per_1m,
    t.output_price_per_1m = s.output_price_per_1m,
    t.cache_read_price_per_1m = s.cache_read_price_per_1m
WHEN NOT MATCHED THEN INSERT
    (model_service, input_price_per_1m, output_price_per_1m, cache_read_price_per_1m, effective_from)
VALUES
    (s.model_service, s.input_price_per_1m, s.output_price_per_1m, s.cache_read_price_per_1m, current_timestamp());
"""
res1 = w.statement_execution.execute_statement(
    warehouse_id=warehouse_id,
    statement=sql_rate_cards,
    wait_timeout="30s"
)
print("rate_cards update:", res1.status.state)

# 2. Update agents table with their designated models
sql_update_models = """
UPDATE sk_inno_aops.agentops_test.agents
SET model_service = CASE
    WHEN agent_id = 'financial-calculator-agent' THEN 'databricks-gpt-5-mini'
    WHEN agent_id = 'doc-summary-agent' THEN 'databricks-claude-sonnet-4-5'
    ELSE 'databricks-meta-llama-3-3-70b-instruct'
END
"""
res2 = w.statement_execution.execute_statement(
    warehouse_id=warehouse_id,
    statement=sql_update_models,
    wait_timeout="30s"
)
print("agents model_service update:", res2.status.state)

# 3. Add weekly release gate records for W40, W41, W42, W43
sql_weekly_gates = """
INSERT INTO sk_inno_aops.agentops_test.release_gates
(gate_id, agent_id, version, checks_json, decision, evidence_ref, decided_by, decided_at, upgrade_type)
VALUES
('gate_w40_1', 'financial-calculator-agent', '0.8.0', '{\"accuracy\": 0.92}', 'approved', 'dbfs:/audit/w40-1.json', 'compliance-officer@saltware.co.kr', timestamp'2026-10-08 10:00:00', 'minor'),
('gate_w40_2', 'doc-summary-agent', '0.8.0', '{\"accuracy\": 0.88}', 'approved', 'dbfs:/audit/w40-2.json', 'lead-architect@saltware.co.kr', timestamp'2026-10-09 14:00:00', 'minor'),
('gate_w41_1', 'test-skill-agent', '0.9.0', '{\"accuracy\": 0.90}', 'approved', 'dbfs:/audit/w41-1.json', 'lead-architect@saltware.co.kr', timestamp'2026-10-15 11:00:00', 'minor'),
('gate_w41_2', 'customer-faq-agent', '0.9.0', '{\"accuracy\": 0.78}', 'rejected', 'dbfs:/audit/w41-2.json', 'lead-architect@saltware.co.kr', timestamp'2026-10-16 16:00:00', 'minor'),
('gate_w42_1', 'financial-calculator-agent', '0.9.0', '{\"accuracy\": 0.95}', 'approved', 'dbfs:/audit/w42-1.json', 'compliance-officer@saltware.co.kr', timestamp'2026-10-22 09:30:00', 'patch'),
('gate_w42_2', 'doc-summary-agent', '0.9.0', '{\"accuracy\": 0.91}', 'approved', 'dbfs:/audit/w42-2.json', 'lead-architect@saltware.co.kr', timestamp'2026-10-23 15:00:00', 'patch'),
('gate_w42_3', 'code-review-agent', '0.1.0', '{\"accuracy\": 0.80}', 'rejected', 'dbfs:/audit/w42-3.json', 'devops-lead@saltware.co.kr', timestamp'2026-10-24 17:00:00', 'major'),
('gate_w43_1', 'test-skill-agent', '1.0.0', '{\"accuracy\": 0.96}', 'approved', 'dbfs:/audit/w43-1.json', 'lead-architect@saltware.co.kr', timestamp'2026-10-29 10:00:00', 'major'),
('gate_w43_2', 'financial-calculator-agent', '1.0.0', '{\"accuracy\": 0.98}', 'approved', 'dbfs:/audit/w43-2.json', 'compliance-officer@saltware.co.kr', timestamp'2026-10-30 11:30:00', 'major'),
('gate_w43_3', 'doc-summary-agent', '1.0.0', '{\"accuracy\": 0.95}', 'approved', 'dbfs:/audit/w43-3.json', 'lead-architect@saltware.co.kr', timestamp'2026-10-31 14:00:00', 'major')
"""
res3 = w.statement_execution.execute_statement(
    warehouse_id=warehouse_id,
    statement=sql_weekly_gates,
    wait_timeout="30s"
)
print("weekly release gates insert:", res3.status.state)
