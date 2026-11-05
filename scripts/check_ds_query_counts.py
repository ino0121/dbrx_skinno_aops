import json

with open("scripts/agentops_dashboard_live.json", "r", encoding="utf-8") as f:
    d = json.load(f)

for ds in d.get("datasets", []):
    ql = ds.get("queryLines", [])
    print(f"Dataset: {ds.get('name')}, lines count: {len(ql)}")
    if len(ql) > 0:
        print("  Query preview: " + "".join(ql)[:120].replace("\n", " "))
    else:
        print("  EMPTY queryLines!")

