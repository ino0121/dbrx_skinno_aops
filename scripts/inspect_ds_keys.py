import json

with open("scripts/agentops_dashboard_live.json", "r", encoding="utf-8") as f:
    d = json.load(f)

for ds in d.get("datasets", [])[:2]:
    print(ds.keys())
    print(ds)

