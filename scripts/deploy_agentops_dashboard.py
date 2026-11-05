import sys
import io
import os
import json
import argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.dashboards import Dashboard

# Default constants
DEFAULT_DASHBOARD_ID = "01f1d7547376159f9e13d0f295497d1d"
DEFAULT_WAREHOUSE_ID = "c4ff4cc877b27739"
SPEC_FILE_PATH = os.path.join(os.path.dirname(__file__), "agentops_dashboard_live.json")

def load_dashboard_spec(file_path: str = SPEC_FILE_PATH) -> dict:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dashboard specification file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def deploy_dashboard(
    profile: str = "dbx_ino0121_saltware",
    dashboard_id: str = DEFAULT_DASHBOARD_ID,
    warehouse_id: str = DEFAULT_WAREHOUSE_ID,
    create_new: bool = False,
    spec_path: str = SPEC_FILE_PATH
):
    w = WorkspaceClient(profile=profile)
    spec_dict = load_dashboard_spec(spec_path)
    serialized_json = json.dumps(spec_dict, ensure_ascii=False)

    display_name = "AgentOps Intelligence Platform"

    if create_new or not dashboard_id:
        print(f"[*] Creating NEW Lakeview Dashboard: '{display_name}'...")
        d = Dashboard(
            display_name=display_name,
            warehouse_id=warehouse_id,
            serialized_dashboard=serialized_json
        )
        created = w.lakeview.create(dashboard=d)
        target_id = created.dashboard_id
        print(f"  -> Dashboard created with new ID: {target_id}")
    else:
        print(f"[*] Updating EXISTING Lakeview Dashboard (ID: {dashboard_id})...")
        d = Dashboard(
            dashboard_id=dashboard_id,
            display_name=display_name,
            warehouse_id=warehouse_id,
            serialized_dashboard=serialized_json
        )
        updated = w.lakeview.update(dashboard_id=dashboard_id, dashboard=d)
        target_id = updated.dashboard_id
        print(f"  -> Dashboard updated successfully (ID: {target_id})")

    print(f"[*] Publishing Dashboard revision...")
    pub = w.lakeview.publish(dashboard_id=target_id)
    print(f"  -> Published Revision Timestamp: {pub.revision_create_time}")

    dashboard_url = f"https://dbc-ee65e920-01b9.cloud.databricks.com/dashboardsv3/{target_id}"

    # Print summary
    pages = spec_dict.get("pages", [])
    datasets = spec_dict.get("datasets", [])
    print("\n================================================================================")
    print("AgentOps Intelligence Platform Deployment Summary")
    print("================================================================================")
    print(f"Dashboard ID:     {target_id}")
    print(f"Display Name:     {display_name}")
    print(f"SQL Warehouse ID: {warehouse_id}")
    print(f"Dashboard URL:    {dashboard_url}")
    print(f"Configured Pages ({len(pages)}):")
    for idx, p in enumerate(pages):
        layout_count = len(p.get("layout", []))
        print(f"  {idx+1}. {p.get('displayName')} [{p.get('name')}] ({layout_count} widgets)")
    print(f"Configured Datasets ({len(datasets)}):")
    for d in datasets:
        print(f"  - {d.get('name')} ({d.get('displayName')})")
    print("================================================================================")
    return target_id, dashboard_url

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy AgentOps AI/BI Lakeview Dashboard")
    parser.add_argument("--create-new", action="store_true", help="Create a completely new dashboard instance instead of updating existing")
    parser.add_argument("--dashboard-id", type=str, default=DEFAULT_DASHBOARD_ID, help="Target dashboard ID to update")
    parser.add_argument("--warehouse-id", type=str, default=DEFAULT_WAREHOUSE_ID, help="SQL Warehouse ID")
    parser.add_argument("--spec", type=str, default=SPEC_FILE_PATH, help="Path to serialized dashboard JSON spec")
    args = parser.parse_args()

    deploy_dashboard(
        dashboard_id=None if args.create_new else args.dashboard_id,
        warehouse_id=args.warehouse_id,
        create_new=args.create_new,
        spec_path=args.spec
    )
