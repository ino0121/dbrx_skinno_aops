from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from databricks.sdk import WorkspaceClient
from codex_agentops.config import load_settings
from codex_agentops.tracing import TraceStore

settings = load_settings()
w = WorkspaceClient(profile=settings.profile)
store = TraceStore(settings.profile, settings.tracing)

trace_id = "8d5e2796a8f93e2d0e4c90f9eee89b20"
full_trace_id = f"trace:/sk_inno_aops.agentops_test.497879688153820/{trace_id}"

print(f"=== [1] MLflow Client로 Trace 조회 ({trace_id}) ===")
trace = store.get(full_trace_id)
print("Trace Info:")
print(f"  Trace ID: {trace.info.trace_id}")
print(f"  Status: {trace.info.state}")
print(f"  Execution Time: {trace.info.execution_time_ms} ms")
print(f"  Total Spans: {len(trace.data.spans)}")

print("\nSpans 목록:")
for i, span in enumerate(trace.data.spans, 1):
    print(f"  [{i}] Span Name: {span.name}, Span Type: {span.span_type}, Span ID: {span.span_id}, Parent ID: {span.parent_id}")
    if span.inputs:
        print(f"      Inputs: {span.inputs}")
    if span.outputs:
        print(f"      Outputs: {span.outputs}")
    if span.attributes:
        print(f"      Attributes (sample):")
        for k in sorted(span.attributes.keys())[:10]:
            print(f"        {k}: {span.attributes[k]}")

# Root Span 전체 Attributes & Tags 덤프
root_span = next(s for s in trace.data.spans if not s.parent_id)
dump_path = Path("C:/projects/agentops/captured_raw_data/verified_trace_dump.json")
trace_dump = {
    "trace_id": trace.info.trace_id,
    "state": str(trace.info.state),
    "execution_time_ms": trace.info.execution_time_ms,
    "tags": trace.info.tags,
    "root_span": {
        "name": root_span.name,
        "span_type": root_span.span_type,
        "inputs": root_span.inputs,
        "outputs": root_span.outputs,
        "attributes": root_span.attributes,
    },
    "child_spans": [
        {
            "name": s.name,
            "span_type": s.span_type,
            "span_id": s.span_id,
            "parent_id": s.parent_id,
            "inputs": s.inputs,
            "outputs": s.outputs,
            "attributes": s.attributes,
        }
        for s in trace.data.spans if s.parent_id
    ]
}
with dump_path.open("w", encoding="utf-8") as f:
    json.dump(trace_dump, f, ensure_ascii=False, indent=2)
print(f"\nTrace 전체 덤프 파일 저장 완료: {dump_path}")

print("\n=== [2] Unity Catalog Delta Table 조회 ===")
sql = f"""
SELECT trace_id, span_id, name, span_type, start_time_unix_nano, end_time_unix_nano
FROM sk_inno_aops.agentops_test.`497879688153820_otel_spans`
LIMIT 10
"""
res = w.statement_execution.execute_statement(
    warehouse_id=settings.warehouse_id,
    statement=sql,
    wait_timeout="30s"
)
print("Delta Table Rows Count:", len(res.result.data_array) if res.result and res.result.data_array else 0)
if res.result and res.result.data_array:
    for row in res.result.data_array:
        print("  Row:", row)

