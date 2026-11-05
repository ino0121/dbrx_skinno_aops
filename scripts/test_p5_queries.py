import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from databricks.sdk import WorkspaceClient

w = WorkspaceClient(profile="dbx_ino0121_saltware")
warehouse_id = "c4ff4cc877b27739"

def test_query(sql, title):
    print(f"\n==================== TEST: {title} ====================")
    resp = w.statement_execution.execute_statement(warehouse_id=warehouse_id, statement=sql, wait_timeout="40s")
    cols = [c.name for c in resp.manifest.schema.columns]
    print(" | ".join(cols))
    print("-" * 60)
    for r in (resp.result.data_array or [])[:5]:
        print(" | ".join(str(x) for x in r))
    print(f"Total rows: {len(resp.result.data_array or [])}")

test_query("""
SELECT
  a.agent_id,
  a.name AS agent_name,
  a.owner_group,
  a.agent_type,
  a.service_criticality,
  a.agent_version,
  CASE WHEN p.agent_id IS NOT NULL THEN 'Production (Deployed)' ELSE 'Registered (Draft)' END AS deployment_status,
  COALESCE(a.model_service, 'databricks-meta-llama-3-3-70b-instruct') AS model_name,
  a.security_level,
  a.data_sensitivity,
  COALESCE(g.decision, 'approved') AS gate_decision
FROM sk_inno_aops.agentops_test.agents a
LEFT JOIN sk_inno_aops.agentops_test.agent_production p ON a.agent_id = p.agent_id
LEFT JOIN (
  SELECT agent_id, decision, ROW_NUMBER() OVER (PARTITION BY agent_id ORDER BY decided_at DESC) as rn
  FROM sk_inno_aops.agentops_test.release_gates
) g ON a.agent_id = g.agent_id AND g.rn = 1
""", "Agent Profile")

test_query("""
SELECT
  s.agent_id,
  COUNT(DISTINCT s.trace_id) AS total_turns,
  ROUND(SUM(CASE WHEN s.status = 'ok' THEN 1 ELSE 0 END) / COUNT(DISTINCT s.trace_id) * 100, 1) AS session_success_rate,
  ROUND(COALESCE(percentile_approx(s.duration_ms, 0.9), 0), 1) AS p90_ms,
  ROUND(COALESCE(AVG(c.total_cost_usd), 0), 5) AS avg_cost_per_turn_usd
FROM sk_inno_aops.agentops_test.v_agentops_spans_summary s
LEFT JOIN sk_inno_aops.agentops_test.v_agentops_cost_summary c ON s.trace_id = c.trace_id
WHERE s.is_root_span = true
GROUP BY s.agent_id
""", "Agent KPIs")

test_query("""
SELECT
  s.agent_id,
  CAST(s.span_timestamp AS STRING) AS executed_at,
  s.session_id,
  s.turn_id,
  COALESCE(s.model_name, 'databricks-meta-llama-3-3-70b-instruct') AS model_name,
  s.duration_ms,
  s.total_tokens,
  s.status,
  CONCAT('https://dbc-ee65e920-01b9.cloud.databricks.com/ml/experiments/497879688153820/traces/', s.trace_id) AS mlflow_trace_url
FROM sk_inno_aops.agentops_test.v_agentops_spans_summary s
WHERE s.is_root_span = true
ORDER BY s.span_timestamp DESC
""", "Agent Trace Logs & Deep Links")

