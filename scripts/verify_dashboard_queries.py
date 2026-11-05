import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from databricks.sdk import WorkspaceClient

w = WorkspaceClient(profile="dbx_ino0121_saltware")
warehouse_id = "c4ff4cc877b27739"

queries = {
    "ds_overview_kpis": """
        SELECT
          (SELECT COUNT(DISTINCT agent_id) FROM sk_inno_aops.agentops_test.agents) AS registered_agents,
          (SELECT COUNT(DISTINCT agent_id) FROM sk_inno_aops.agentops_test.agent_production) AS deployed_agents,
          (SELECT COUNT(DISTINCT user_id) FROM sk_inno_aops.agentops_test.v_agentops_spans_summary WHERE is_root_span = true AND user_id IS NOT NULL) AS dau,
          (SELECT ROUND(SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) / COUNT(DISTINCT trace_id) * 100, 1) FROM sk_inno_aops.agentops_test.v_agentops_spans_summary WHERE is_root_span = true) AS session_success_rate
    """,
    "ds_overview_agent_traffic": """
        SELECT
          COALESCE(agent_id, 'unknown') AS agent_id,
          COUNT(DISTINCT session_id) AS session_count,
          COUNT(DISTINCT trace_id) AS turn_count
        FROM sk_inno_aops.agentops_test.v_agentops_spans_summary
        WHERE is_root_span = true
        GROUP BY COALESCE(agent_id, 'unknown')
    """,
    "ds_quality_kpis": """
        SELECT
          (SELECT ROUND(percentile_approx(duration_ms, 0.5), 1) FROM sk_inno_aops.agentops_test.v_agentops_spans_summary WHERE is_root_span = true) AS latency_p50_ms,
          (SELECT ROUND(percentile_approx(duration_ms, 0.9), 1) FROM sk_inno_aops.agentops_test.v_agentops_spans_summary WHERE is_root_span = true) AS latency_p90_ms,
          (SELECT ROUND(SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) / COUNT(DISTINCT trace_id) * 100, 1) FROM sk_inno_aops.agentops_test.v_agentops_spans_summary WHERE is_root_span = true) AS system_error_rate,
          (SELECT ROUND(AVG(rating), 2) FROM sk_inno_aops.agentops_test.review_app_feedbacks) AS avg_hitl_rating
    """,
    "ds_governance_kpis": """
        SELECT
          (SELECT COUNT(*) FROM sk_inno_aops.agentops_test.agent_versions) AS registered_versions,
          (SELECT COUNT(*) FROM sk_inno_aops.agentops_test.agent_production) AS active_production_pointers,
          (SELECT COUNT(*) FROM sk_inno_aops.agentops_test.release_gates WHERE decision = 'approved') AS release_gates_passed,
          (SELECT COUNT(*) FROM sk_inno_aops.agentops_test.v_agentops_spans_summary WHERE is_root_span = true AND agent_revision = 'working') AS abnormal_working_revisions
    """,
    "ds_cost_kpis": """
        SELECT
          (SELECT ROUND(COALESCE(SUM(total_cost_usd), 0), 4) FROM sk_inno_aops.agentops_test.v_agentops_cost_summary) AS total_cost_usd,
          (SELECT COALESCE(SUM(total_tokens), 0) FROM sk_inno_aops.agentops_test.v_agentops_spans_summary) AS total_tokens,
          (SELECT COALESCE(SUM(prompt_tokens), 0) FROM sk_inno_aops.agentops_test.v_agentops_spans_summary) AS prompt_tokens,
          (SELECT COALESCE(SUM(completion_tokens), 0) FROM sk_inno_aops.agentops_test.v_agentops_spans_summary) AS completion_tokens
    """
}

for name, sql in queries.items():
    res = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=sql,
        wait_timeout="30s"
    )
    print(f"[{name}] status: {res.status.state}")
    if res.status.error:
        print(f"  Error: {res.status.error.message}")
    elif res.result and res.result.data_array:
        print(f"  Result: {res.result.data_array[0]}")
