import sys
import io
import json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open("scripts/agentops_dashboard_live.json", "r", encoding="utf-8") as f:
    d = json.load(f)

for p_idx, p in enumerate(d.get("pages", [])):
    print(f"\n==================================================")
    print(f"Page {p_idx+1}: {p.get('displayName')} ({p.get('name')})")
    print(f"==================================================")
    for w_idx, item in enumerate(p.get("layout", [])):
        widget = item.get("widget", {})
        spec = widget.get("spec", {})
        w_type = spec.get("widgetType") or "textbox/other"
        w_title = spec.get("frame", {}).get("title") or spec.get("title") or widget.get("name")
        queries = widget.get("queries", [])
        ds_names = [q.get("query", {}).get("datasetName") for q in queries]
        fields = []
        for q in queries:
            fields.extend([f.get("name") for f in q.get("query", {}).get("fields", [])])
        print(f"  [{w_idx+1}] {w_type:<18} | Title: {str(w_title):<35} | Datasets: {ds_names} | Fields: {fields}")

