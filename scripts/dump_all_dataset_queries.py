import json

with open("scripts/agentops_dashboard_live.json", "r", encoding="utf-8") as f:
    d = json.load(f)

for idx, ds in enumerate(d.get("datasets", [])):
    name = ds.get("name")
    disp = ds.get("displayName")
    ql = "".join(ds.get("queryLines", [])).strip()
    print(f"\n==================================================")
    print(f"[{idx+1}] {name} ({disp})")
    print(f"==================================================")
    print(ql)

