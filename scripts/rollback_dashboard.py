import sys
import io
import json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.dashboards import Dashboard

w = WorkspaceClient(profile="dbx_ino0121_saltware")
warehouse_id = "c4ff4cc877b27739"
dashboard_id = "01f1d7547376159f9e13d0f295497d1d"

def qlines(sql: str):
    return [line + "\n" for line in sql.strip().split("\n")]

print(f"Fetching current live dashboard (ID: {dashboard_id})...")
live_dash = w.lakeview.get(dashboard_id)
dash_dict = json.loads(live_dash.serialized_dashboard)

# 1. Page 1에서 인라인 상세 위젯 제거하고 원래 8개 위젯만 유지
p1 = [p for p in dash_dict["pages"] if p["name"] == "page_overview"][0]
orig_p1_names = [
    "p1_header", "ov_kpi_1", "ov_kpi_2", "ov_kpi_3", "ov_kpi_4",
    "ov_chart_1", "ov_chart_2", "ov_table_outliers"
]
p1["layout"] = [it for it in p1["layout"] if it.get("widget", {}).get("name") in orig_p1_names]

# ov_table_outliers 컬럼 원복 (latest_trace_url 제거)
for it in p1["layout"]:
    if it.get("widget", {}).get("name") == "ov_table_outliers":
        fields = it["widget"]["queries"][0]["query"]["fields"]
        it["widget"]["queries"][0]["query"]["fields"] = [f for f in fields if f.get("name") != "latest_trace_url"]
        cols = it["widget"]["spec"]["encodings"]["columns"]
        it["widget"]["spec"]["encodings"]["columns"] = [c for c in cols if c.get("fieldName") != "latest_trace_url"]

# 2. ds_p1_table_outliers 쿼리 원복
orig_outliers_sql = """
SELECT
  COALESCE(s.agent_id, a.agent_id) AS agent_id,
  COALESCE(a.agent_type, 'Skill-based') AS agent_type,
  COALESCE(a.owner_group, 'AI-CoE') AS owner_group,
  COALESCE(a.service_criticality, '중') AS service_criticality,
  COALESCE(s.agent_revision, 'working') AS agent_revision,
  COUNT(DISTINCT s.trace_id) AS turn_count,
  ROUND(COALESCE(percentile_approx(s.duration_ms, 0.9), 0), 1) AS p90_duration_ms,
  ROUND(SUM(CASE WHEN s.status = 'error' THEN 1 ELSE 0 END) / COUNT(DISTINCT s.trace_id) * 100, 1) AS error_rate,
  CASE WHEN s.agent_revision = 'working' THEN 'Alert (working)'
       WHEN SUM(CASE WHEN s.status = 'error' THEN 1 ELSE 0 END) > 0 THEN 'Warning'
       ELSE 'Normal (OK)' END AS operational_status
FROM sk_inno_aops.agentops_test.v_agentops_spans_summary s
LEFT JOIN sk_inno_aops.agentops_test.agents a ON s.agent_id = a.agent_id
WHERE s.is_root_span = true
GROUP BY COALESCE(s.agent_id, a.agent_id), a.agent_type, a.owner_group, a.service_criticality, s.agent_revision
ORDER BY p90_duration_ms DESC
"""

# 3. Datasets에서 ds_p5_* 제거하고 원래 16개 데이터셋만 유지
orig_ds_names = {
    "ds_p1_kpis", "ds_p1_chart_dau", "ds_p1_chart_latency", "ds_p1_table_outliers",
    "ds_p2_kpis", "ds_p2_chart_quality_trend", "ds_p2_chart_tools", "ds_p2_table_quality",
    "ds_p3_kpis", "ds_p3_chart_cadence_combo", "ds_p3_chart_security", "ds_p3_table_audit",
    "ds_p4_kpis", "ds_p4_chart_token_breakdown", "ds_p4_chart_model_tokens", "ds_p4_table_efficiency"
}
filtered_datasets = []
for ds in dash_dict.get("datasets", []):
    if ds["name"] in orig_ds_names:
        if ds["name"] == "ds_p1_table_outliers":
            ds["queryLines"] = qlines(orig_outliers_sql)
        filtered_datasets.append(ds)
dash_dict["datasets"] = filtered_datasets

# 4. Pages는 오직 원래 4개 페이지만 유지
dash_dict["pages"] = [p for p in dash_dict.get("pages", []) if p["name"] in ("page_overview", "page_quality", "page_governance", "page_cost")]

# 백업 파일 저장
with open("scripts/dashboard_rolled_back.json", "w", encoding="utf-8") as f:
    json.dump(dash_dict, f, indent=2, ensure_ascii=False)
print("Saved rollback backup to scripts/dashboard_rolled_back.json")

# Databricks API 호출
print(f"Rolling back dashboard to original 4 clean pages (ID: {dashboard_id})...")
updated = w.lakeview.update(
    dashboard_id=dashboard_id,
    dashboard=Dashboard(
        display_name="AgentOps Intelligence Platform",
        warehouse_id=warehouse_id,
        serialized_dashboard=json.dumps(dash_dict, ensure_ascii=False)
    )
)
print("Dashboard rollback update succeeded!")

print("Publishing rolled back dashboard...")
pub = w.lakeview.publish(dashboard_id=dashboard_id)
print(f"Published revision at: {pub.revision_create_time}")

dashboard_url = f"https://dbc-ee65e920-01b9.cloud.databricks.com/dashboardsv3/{dashboard_id}"
print("================================================================================")
print("Rolled Back Clean Dashboard URL:")
print(dashboard_url)
print("================================================================================")

