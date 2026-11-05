import json

with open("scripts/agentops_dashboard_live.json", "r", encoding="utf-8") as f:
    d = json.load(f)

p5 = d.get("pages")[4]
print("=== Page 5 Widgets ===")
for idx, w in enumerate(p5.get("layout", [])):
    widget = w.get("widget", {})
    w_title = widget.get("spec", {}).get("frame", {}).get("title") or widget.get("spec", {}).get("widgetType") or "textbox/other"
    queries = widget.get("queries", [])
    ds_names = [q.get("query", {}).get("datasetName") for q in queries]
    print(f"Widget {idx+1}: title='{w_title}', type='{widget.get('spec', {}).get('widgetType')}', datasets={ds_names}")

