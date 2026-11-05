from codex_agentops.config import load_settings
from codex_agentops.mlflow_exporter import export_pending
from codex_agentops.outbox import Outbox
from codex_agentops.paths import outbox_path

settings = load_settings()
outbox = Outbox(outbox_path())

with outbox._connect() as conn:
    conn.execute("UPDATE turn_uploads SET status = 'pending', lease_until_ns = 0 WHERE status != 'uploaded'")
    conn.commit()

res = export_pending(outbox, settings, limit=10, require_usage=False)
print(f"Remaining uploaded: {res.uploaded}, Failed: {res.failed}")
for tid in res.trace_ids:
    print(f"  Trace: {tid}")
