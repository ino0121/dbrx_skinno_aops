import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from databricks.sdk import WorkspaceClient

w = WorkspaceClient(profile="dbx_ino0121_saltware")
warehouse_id = "c4ff4cc877b27739"

# 1. Update v_agentops_spans_summary
sql_spans_view = """
CREATE OR REPLACE VIEW sk_inno_aops.agentops_test.v_agentops_spans_summary AS
WITH raw_spans AS (
    SELECT
        trace_id,
        span_id,
        parent_span_id,
        name AS span_name,
        time AS span_timestamp,
        date AS span_date,
        ROUND((end_time_unix_nano - start_time_unix_nano) / 1000000.0, 2) AS duration_ms,
        CASE WHEN parent_span_id IS NULL THEN true ELSE false END AS is_root_span,
        CASE 
            WHEN name = 'agent.session' THEN 'session'
            WHEN name = 'agent.turn' THEN 'turn'
            WHEN name LIKE 'turn.%' THEN 'turn_child'
            ELSE 'component'
        END AS span_level,
        CASE 
            WHEN name = 'agent.turn' THEN 'TURN'
            WHEN name LIKE 'tool.%' THEN 'TOOL'
            WHEN name LIKE 'agent.subagent.%' THEN 'SUBAGENT'
            WHEN name = 'agent.session' THEN 'SESSION'
            WHEN name LIKE 'turn.%' THEN 'TURN'
            ELSE 'OTHER'
        END AS span_type,
        try_variant_get(attributes, '$["agentops.agent_id"]', 'string') AS raw_agent_id,
        try_variant_get(attributes, '$["agentops.agent_version"]', 'string') AS raw_agent_version,
        try_variant_get(attributes, '$["agentops.agent_revision"]', 'string') AS raw_agent_revision,
        try_variant_get(attributes, '$["agentops.session_id"]', 'string') AS raw_session_id,
        try_variant_get(attributes, '$["agentops.turn_id"]', 'string') AS turn_id,
        try_variant_get(attributes, '$["user.id"]', 'string') AS raw_user_id,
        CASE 
            WHEN LOWER(try_variant_get(attributes, '$["agentops.status"]', 'string')) IN ('ok', 'error') 
                THEN LOWER(try_variant_get(attributes, '$["agentops.status"]', 'string'))
            WHEN status.code = 'STATUS_CODE_OK' THEN 'ok'
            WHEN status.code = 'STATUS_CODE_ERROR' THEN 'error'
            ELSE 'ok'
        END AS status,
        try_variant_get(attributes, '$["agentops.error_type"]', 'string') AS error_type,
        COALESCE(
            try_variant_get(attributes, '$["agentops.model"]', 'string'),
            try_variant_get(attributes, '$["gen_ai.response.model"]', 'string')
        ) AS model_name,
        -- turn.* sub-spans under agent.session duplicate the tokens of the standalone turn, zero them out to prevent double counting
        CASE 
            WHEN name LIKE 'turn.%' THEN 0
            ELSE COALESCE(
                CAST(try_variant_get(attributes, '$["agentops.tokens.input"]', 'int') AS INT),
                CAST(try_variant_get(attributes, '$["gen_ai.usage.prompt_tokens"]', 'int') AS INT),
                0
            )
        END AS prompt_tokens,
        CASE 
            WHEN name LIKE 'turn.%' THEN 0
            ELSE COALESCE(
                CAST(try_variant_get(attributes, '$["agentops.tokens.output"]', 'int') AS INT),
                CAST(try_variant_get(attributes, '$["gen_ai.usage.completion_tokens"]', 'int') AS INT),
                0
            )
        END AS completion_tokens,
        CASE 
            WHEN name LIKE 'turn.%' THEN 0
            ELSE COALESCE(
                CAST(try_variant_get(attributes, '$["agentops.tokens.total"]', 'int') AS INT),
                CAST(try_variant_get(attributes, '$["gen_ai.usage.total_tokens"]', 'int') AS INT),
                0
            )
        END AS total_tokens,
        COALESCE(
            try_variant_get(attributes, '$["mlflow.experimentId"]', 'string'),
            '497879688153820'
        ) AS experiment_id
    FROM sk_inno_aops.agentops_test.`497879688153820_otel_spans`
    WHERE name != 'agentops.configuration-test'
),
trace_inherited AS (
    SELECT
        trace_id,
        span_id,
        parent_span_id,
        span_name,
        span_timestamp,
        span_date,
        duration_ms,
        is_root_span,
        span_level,
        span_type,
        COALESCE(
            raw_agent_id,
            FIRST_VALUE(raw_agent_id, true) OVER (
                PARTITION BY trace_id 
                ORDER BY CASE WHEN span_name = 'agent.turn' THEN 1 WHEN span_name = 'agent.session' THEN 2 ELSE 3 END
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ),
            'unknown'
        ) AS agent_id,
        COALESCE(
            raw_agent_version,
            FIRST_VALUE(raw_agent_version, true) OVER (
                PARTITION BY trace_id 
                ORDER BY CASE WHEN span_name = 'agent.turn' THEN 1 WHEN span_name = 'agent.session' THEN 2 ELSE 3 END
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            )
        ) AS agent_version,
        COALESCE(
            raw_agent_revision,
            FIRST_VALUE(raw_agent_revision, true) OVER (
                PARTITION BY trace_id 
                ORDER BY CASE WHEN span_name = 'agent.turn' THEN 1 WHEN span_name = 'agent.session' THEN 2 ELSE 3 END
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            )
        ) AS raw_agent_revision_inherited,
        COALESCE(
            raw_session_id,
            FIRST_VALUE(raw_session_id, true) OVER (
                PARTITION BY trace_id 
                ORDER BY CASE WHEN span_name = 'agent.turn' THEN 1 WHEN span_name = 'agent.session' THEN 2 ELSE 3 END
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            )
        ) AS session_id,
        turn_id,
        COALESCE(
            raw_user_id,
            FIRST_VALUE(raw_user_id, true) OVER (
                PARTITION BY trace_id 
                ORDER BY CASE WHEN span_name = 'agent.turn' THEN 1 WHEN span_name = 'agent.session' THEN 2 ELSE 3 END
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            )
        ) AS user_id,
        status,
        error_type,
        model_name,
        prompt_tokens,
        completion_tokens,
        total_tokens,
        experiment_id
    FROM raw_spans
)
SELECT 
    t.trace_id,
    t.span_id,
    t.parent_span_id,
    t.span_name,
    t.span_timestamp,
    t.span_date,
    t.duration_ms,
    t.is_root_span,
    t.span_level,
    t.span_type,
    t.agent_id,
    t.agent_version,
    CASE 
        WHEN p.agent_id IS NOT NULL AND (p.version = t.agent_version OR p.version IS NULL) THEN 'prod'
        WHEN t.raw_agent_revision_inherited = 'prod' THEN 'prod'
        ELSE 'working'
    END AS agent_revision,
    t.session_id,
    t.turn_id,
    t.user_id,
    t.status,
    t.error_type,
    t.model_name,
    t.prompt_tokens,
    t.completion_tokens,
    t.total_tokens,
    t.experiment_id
FROM trace_inherited t
LEFT JOIN (
    SELECT agent_id, version,
           ROW_NUMBER() OVER (PARTITION BY agent_id ORDER BY updated_at DESC) rn
    FROM sk_inno_aops.agentops_test.agent_production
) p ON t.agent_id = p.agent_id AND p.rn = 1;
"""

# 2. Update v_agentops_cost_summary
sql_cost_view = """
CREATE OR REPLACE VIEW sk_inno_aops.agentops_test.v_agentops_cost_summary AS
SELECT
    s.trace_id,
    s.span_id,
    s.is_root_span,
    s.span_level,
    s.span_type,
    s.span_timestamp,
    s.span_date,
    s.agent_id,
    s.agent_version,
    s.agent_revision,
    s.session_id,
    s.turn_id,
    s.model_name,
    s.prompt_tokens,
    s.completion_tokens,
    s.total_tokens,
    s.status,
    COALESCE(r.input_price_per_1m, 0.40) AS input_price_per_1m,
    COALESCE(r.output_price_per_1m, 1.20) AS output_price_per_1m,
    ROUND(
        (s.prompt_tokens * COALESCE(r.input_price_per_1m, 0.40) / 1000000.0) +
        (s.completion_tokens * COALESCE(r.output_price_per_1m, 1.20) / 1000000.0),
        6
    ) AS total_cost_usd
FROM sk_inno_aops.agentops_test.v_agentops_spans_summary s
LEFT JOIN sk_inno_aops.agentops_test.rate_cards r
    ON s.model_name = r.model_service;
"""

# 3. Update v_agentops_turns
sql_turns_view = """
CREATE OR REPLACE VIEW sk_inno_aops.agentops_test.v_agentops_turns AS
WITH trace_costs AS (
    SELECT 
        trace_id,
        ROUND(SUM(total_cost_usd), 6) AS trace_cost_usd
    FROM sk_inno_aops.agentops_test.v_agentops_cost_summary
    GROUP BY trace_id
)
SELECT
    s.trace_id,
    s.span_timestamp,
    s.span_date,
    s.session_id,
    s.turn_id,
    s.agent_id,
    s.agent_version,
    s.agent_revision,
    s.model_name,
    s.duration_ms,
    s.prompt_tokens,
    s.completion_tokens,
    s.total_tokens,
    s.status,
    COALESCE(c.trace_cost_usd, 0.0) AS total_cost_usd,
    CONCAT(
        'https://dbc-ee65e920-01b9.cloud.databricks.com/ml/experiments/',
        s.experiment_id,
        '/traces/',
        s.trace_id
    ) AS trace_link
FROM sk_inno_aops.agentops_test.v_agentops_spans_summary s
LEFT JOIN trace_costs c ON s.trace_id = c.trace_id
WHERE s.span_name = 'agent.turn';
"""

# 4. Update v_agentops_component_spans
sql_comp_view = """
CREATE OR REPLACE VIEW sk_inno_aops.agentops_test.v_agentops_component_spans AS
SELECT
    s.trace_id,
    s.span_id,
    s.span_timestamp,
    s.span_date,
    s.agent_id,
    CASE 
        WHEN s.span_name LIKE 'tool.%' THEN 'tool'
        WHEN s.span_name LIKE 'agent.subagent.%' THEN 'subagent'
        ELSE 'component'
    END AS component_type,
    CASE 
        WHEN s.span_name LIKE 'tool.%' THEN SUBSTRING(s.span_name, 6)
        WHEN s.span_name LIKE 'agent.subagent.%' THEN SUBSTRING(s.span_name, 16)
        ELSE s.span_name
    END AS component_name,
    s.duration_ms,
    s.status
FROM sk_inno_aops.agentops_test.v_agentops_spans_summary s
WHERE s.span_name LIKE 'tool.%' OR s.span_name LIKE 'agent.subagent.%';
"""

# 5. v_agentops_agent_profile
sql_profile_view = """
CREATE OR REPLACE VIEW sk_inno_aops.agentops_test.v_agentops_agent_profile AS
WITH latest_rev AS (
  SELECT agent_id, agent_revision FROM (
    SELECT agent_id, agent_revision,
           ROW_NUMBER() OVER (PARTITION BY agent_id ORDER BY span_timestamp DESC) rn
    FROM sk_inno_aops.agentops_test.v_agentops_spans_summary
    WHERE agent_id IS NOT NULL) WHERE rn = 1
),
prod AS (
  SELECT agent_id, version FROM (
    SELECT agent_id, version,
           ROW_NUMBER() OVER (PARTITION BY agent_id ORDER BY updated_at DESC) rn
    FROM sk_inno_aops.agentops_test.agent_production) WHERE rn = 1
),
gate AS (
  SELECT agent_id, decision, decided_at FROM (
    SELECT g.agent_id, g.decision, g.decided_at,
           ROW_NUMBER() OVER (PARTITION BY g.agent_id ORDER BY g.decided_at DESC) rn
    FROM sk_inno_aops.agentops_test.release_gates g
    JOIN sk_inno_aops.agentops_test.agents a
      ON g.agent_id = a.agent_id AND g.version = a.agent_version) WHERE rn = 1
)
SELECT a.agent_id, a.name, a.owner_group, a.agent_type, a.service_criticality,
       a.agent_version,
       COALESCE(r.agent_revision, 'N/A') AS agent_revision,
       CASE WHEN p.agent_id IS NOT NULL THEN 'Deployed' ELSE 'Registered' END AS deployment_status,
       p.version AS production_version,
       a.model_service, a.security_level, a.data_sensitivity,
       COALESCE(g.decision, 'no_gate') AS gate_decision,
       g.decided_at AS gate_decided_at
FROM sk_inno_aops.agentops_test.agents a
LEFT JOIN latest_rev r ON a.agent_id = r.agent_id
LEFT JOIN prod p       ON a.agent_id = p.agent_id
LEFT JOIN gate g       ON a.agent_id = g.agent_id;
"""

if __name__ == "__main__":
    for name, sql in [
        ("v_agentops_spans_summary", sql_spans_view),
        ("v_agentops_cost_summary", sql_cost_view),
        ("v_agentops_turns", sql_turns_view),
        ("v_agentops_component_spans", sql_comp_view),
        ("v_agentops_agent_profile", sql_profile_view)
    ]:
        res = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=sql,
            wait_timeout="50s"
        )
        print(f"[{name}] status: {res.status.state}")
        if res.status.error:
            print(f"  Error: {res.status.error.message}")
