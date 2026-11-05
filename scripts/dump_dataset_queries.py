import json

with open("scripts/agentops_dashboard_live.json", "r", encoding="utf-8") as f:
    d = json.load(f)

print("=== 20 DATASETS SQL ANALYSIS ===")
for idx, ds in enumerate(d.get("datasets", [])):
    name = ds.get("name")
    disp = ds.get("displayName")
    q = ds.get("query", "").strip()
    print(f"\n[{idx+1}] {name} ({disp})")
    print("-" * 50)
    print(q)

