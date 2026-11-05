import sys
import io
import json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from databricks.sdk import WorkspaceClient

w = WorkspaceClient(profile="dbx_ino0121_saltware")
wh_id = "c4ff4cc877b27739"

print("================================================================================")
print("TASK 1. 뷰 생성 (sk_inno_aops.agentops_test.v_agentops_agent_profile)")
print("================================================================================")

view_sql = """
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

print("Executing CREATE OR REPLACE VIEW...")
res_view = w.statement_execution.execute_statement(
    warehouse_id=wh_id,
    statement=view_sql,
    wait_timeout="40s"
)
print("View created successfully! Statement ID:", res_view.statement_id)

print("\nVerifying View schema and initial rows:")
res_v_check = w.statement_execution.execute_statement(
    warehouse_id=wh_id,
    statement="SELECT * FROM sk_inno_aops.agentops_test.v_agentops_agent_profile ORDER BY agent_id",
    wait_timeout="30s"
)
v_cols = [c.name for c in res_v_check.manifest.schema.columns]
print("View Columns:", v_cols)
for r in res_v_check.result.data_array or []:
    print(" ", r)

print("\n================================================================================")
print("TASK 2. 원본 테이블(agents) security_level 업데이트")
print("================================================================================")

# 2.1 변경 전 테이블 히스토리 조회 (이전 버전 번호 확인)
print("[조건 5] 변경 전 테이블 버전 번호 확인:")
res_hist = w.statement_execution.execute_statement(
    warehouse_id=wh_id,
    statement="DESCRIBE HISTORY sk_inno_aops.agentops_test.agents LIMIT 1",
    wait_timeout="30s"
)
h_cols = [c.name for c in res_hist.manifest.schema.columns]
curr_version = res_hist.result.data_array[0][h_cols.index("version")]
curr_ts = res_hist.result.data_array[0][h_cols.index("timestamp")]
print(f"  -> 현재 최신 테이블 버전: VERSION {curr_version} (생성 시각: {curr_ts})")
print(f"  -> 문제 발생 시 복구 명령어: RESTORE TABLE sk_inno_aops.agentops_test.agents TO VERSION AS OF {curr_version}")

# 2.2 변경 전 5개 행 조회
print("\n[조건 1] 변경 전 대상 5개 행의 agent_id, security_level, updated_at:")
res_before = w.statement_execution.execute_statement(
    warehouse_id=wh_id,
    statement="""
    SELECT agent_id, security_level, CAST(updated_at AS STRING) as updated_at
    FROM sk_inno_aops.agentops_test.agents
    ORDER BY agent_id
    """,
    wait_timeout="30s"
)
print("  agent_id | security_level | updated_at")
print("  " + "-" * 55)
for r in res_before.result.data_array:
    print(f"  {r[0]:<28} | {r[1]:<6} | {r[2]}")

# 2.3 변경 대상 3건 업데이트 실행
update_sql = """
UPDATE sk_inno_aops.agentops_test.agents
SET security_level = CASE
      WHEN agent_id = 'financial-calculator-agent' THEN '기밀'
      WHEN agent_id = 'code-review-agent' THEN '중요'
      WHEN agent_id = 'test-skill-agent' THEN '중요'
    END,
    updated_at = current_timestamp()
WHERE agent_id IN ('financial-calculator-agent', 'code-review-agent', 'test-skill-agent')
"""

print("\n[조건 2, 3] 대상 3개 행 업데이트 실행...")
res_upd = w.statement_execution.execute_statement(
    warehouse_id=wh_id,
    statement=update_sql,
    wait_timeout="40s"
)

# 2.4 영향 받은 행 수 확인 (DESCRIBE HISTORY operationMetrics)
res_hist_after = w.statement_execution.execute_statement(
    warehouse_id=wh_id,
    statement="DESCRIBE HISTORY sk_inno_aops.agentops_test.agents LIMIT 1",
    wait_timeout="30s"
)
h_after_cols = [c.name for c in res_hist_after.manifest.schema.columns]
op_metrics = res_hist_after.result.data_array[0][h_after_cols.index("operationMetrics")]
new_version = res_hist_after.result.data_array[0][h_after_cols.index("version")]
print(f"  -> 업데이트 후 신규 버전: VERSION {new_version}")
print(f"  -> Delta Operation Metrics: {op_metrics}")

# numUpdatedRows 파싱 확인
target_rows_updated = None
if isinstance(op_metrics, dict):
    target_rows_updated = int(op_metrics.get("numUpdatedRows", op_metrics.get("numTargetRowsUpdated", -1)))
elif isinstance(op_metrics, str):
    import ast
    try:
        m_dict = json.loads(op_metrics)
    except:
        try:
            m_dict = ast.literal_eval(op_metrics)
        except:
            m_dict = {}
    target_rows_updated = int(m_dict.get("numUpdatedRows", m_dict.get("numTargetRowsUpdated", -1)))

print(f"  -> 영향 받은 행 수(numTargetRowsUpdated): {target_rows_updated}")
if target_rows_updated != 3:
    raise RuntimeError(f"[ABORT] 영향 받는 행이 3건이 아닙니다! (실제: {target_rows_updated}건). 작업을 중단합니다.")
print("  -> 영향 받는 행이 정확히 3건임을 검증 완료했습니다.")

# 2.5 변경 후 5개 행 조회
print("\n[조건 4-1] 변경 후 5개 행의 agent_id, security_level, updated_at:")
res_after = w.statement_execution.execute_statement(
    warehouse_id=wh_id,
    statement="""
    SELECT agent_id, security_level, CAST(updated_at AS STRING) as updated_at
    FROM sk_inno_aops.agentops_test.agents
    ORDER BY agent_id
    """,
    wait_timeout="30s"
)
print("  agent_id | security_level | updated_at")
print("  " + "-" * 55)
for r in res_after.result.data_array:
    print(f"  {r[0]:<28} | {r[1]:<6} | {r[2]}")

# 2.6 security_level별 건수 검증 (기밀 1 / 중요 2 / 일반 2)
print("\n[조건 4-2] security_level별 집계 건수 검증:")
res_dist = w.statement_execution.execute_statement(
    warehouse_id=wh_id,
    statement="""
    SELECT security_level, COUNT(*) as cnt
    FROM sk_inno_aops.agentops_test.agents
    GROUP BY security_level
    ORDER BY CASE security_level WHEN '기밀' THEN 1 WHEN '중요' THEN 2 WHEN '일반' THEN 3 ELSE 4 END
    """,
    wait_timeout="30s"
)
dist_dict = {}
for r in res_dist.result.data_array:
    print(f"  {r[0]}: {r[1]}건")
    dist_dict[r[0]] = int(r[1])

assert dist_dict.get("기밀") == 1, f"기밀 건수가 1이 아닙니다: {dist_dict.get('기밀')}"
assert dist_dict.get("중요") == 2, f"중요 건수가 2가 아닙니다: {dist_dict.get('중요')}"
assert dist_dict.get("일반") == 2, f"일반 건수가 2가 아닙니다: {dist_dict.get('일반')}"
print("  -> 검증 완료: 기밀 1 / 중요 2 / 일반 2 정합성 일치!")

# 2.7 뷰(v_agentops_agent_profile) 최종 반영 상태 확인
print("\n[최종 검증] 생성된 뷰(v_agentops_agent_profile)에서의 security_level 반영 확인:")
res_v_final = w.statement_execution.execute_statement(
    warehouse_id=wh_id,
    statement="SELECT agent_id, name, security_level, deployment_status, gate_decision FROM sk_inno_aops.agentops_test.v_agentops_agent_profile ORDER BY agent_id",
    wait_timeout="30s"
)
for r in res_v_final.result.data_array:
    print(f"  {r[0]:<28} | {r[1]:<26} | 보안: {r[2]:<4} | 상태: {r[3]:<10} | 게이트: {r[4]}")

print("\n모든 작업이 완벽하게 완료되었습니다.")
