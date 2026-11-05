import collections
import json
import re
import sys
import time
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

from codex_agentops.config import load_settings
from codex_agentops.hooks import handle_hook
from codex_agentops.mlflow_exporter import export_pending
from codex_agentops.outbox import Outbox
from codex_agentops.paths import outbox_path

w = WorkspaceClient(profile="dbx_ino0121_saltware")

def run_gpt_turn(turn_idx: int, amount: int):
    root = Path(r"c:\projects\agentops\financial-calculator-agent")
    session_id = f"ses_gpt_{uuid.uuid4().hex[:8]}"
    turn_id = f"turn_01{turn_idx}"
    model_name = "databricks-gpt-5-mini"

    print(f"\n[financial-calculator-agent] Invoking {model_name} for Amount={amount:,}...")
    t0 = time.time()

    handle_hook({
        "hook_event_name": "SessionStart",
        "session_id": session_id,
        "model": model_name,
        "cwd": str(root),
    }, launch_uploader=False)

    handle_hook({
        "hook_event_name": "UserPromptSubmit",
        "session_id": session_id,
        "turn_id": turn_id,
        "prompt": f"거래 총액 {amount:,}원의 공급가액과 부가세를 계산하고 세법 감사를 진행해줘.",
        "model": model_name,
        "cwd": str(root),
    }, launch_uploader=False)

    tool_call_id = f"call_vat_{uuid.uuid4().hex[:8]}"
    handle_hook({
        "hook_event_name": "PreToolUse",
        "session_id": session_id,
        "turn_id": turn_id,
        "tool_name": "vat_calculator",
        "tool_use_id": tool_call_id,
        "cwd": str(root),
    }, launch_uploader=False)

    supply_val = round(amount / 1.1)
    vat_val = amount - supply_val
    tool_res = {"gross_amount": amount, "supply_value": supply_val, "vat_value": vat_val}

    handle_hook({
        "hook_event_name": "PostToolUse",
        "session_id": session_id,
        "turn_id": turn_id,
        "tool_name": "vat_calculator",
        "tool_use_id": tool_call_id,
        "tool_result": json.dumps(tool_res),
        "cwd": str(root),
    }, launch_uploader=False)

    sub_id = "tax-auditor"
    handle_hook({
        "hook_event_name": "SubagentStart",
        "session_id": session_id,
        "turn_id": turn_id,
        "agent_id": sub_id,
        "agent_type": "skill-based-subagent",
        "cwd": str(root),
    }, launch_uploader=False)

    prompt = f"세무 감사 의견: 공급가액 {supply_val:,}원과 부가세 {vat_val:,}원이 적법한지 간결하게 답변하세요."
    resp = w.serving_endpoints.query(
        name=model_name,
        messages=[ChatMessage(role=ChatMessageRole.USER, content=prompt)],
        max_tokens=50
    )
    opinion = resp.choices[0].message.content.strip()
    u = resp.usage.as_dict() if resp.usage else {"prompt_tokens": 70, "completion_tokens": 40, "total_tokens": 110}

    handle_hook({
        "hook_event_name": "SubagentStop",
        "session_id": session_id,
        "turn_id": turn_id,
        "agent_id": sub_id,
        "agent_type": "skill-based-subagent",
        "cwd": str(root),
    }, launch_uploader=False)

    transcript_file = root / ".system_generated" / "logs" / "transcript.jsonl"
    transcript_file.parent.mkdir(parents=True, exist_ok=True)
    with transcript_file.open("a", encoding="utf-8") as f:
        rec = {
            "type": "token_usage_record",
            "payload": {
                "session_id": session_id,
                "turn_id": turn_id,
                "timestamp": time.time(),
                "model": model_name,
                "usage": {
                    "input_tokens": u.get("prompt_tokens", 70),
                    "output_tokens": u.get("completion_tokens", 40),
                    "total_tokens": u.get("total_tokens", 110),
                    "cached_input_tokens": 0
                }
            }
        }
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    final_msg = f"도구 계산({tool_res}) 및 서브에이전트 감사({opinion}) 완료."
    handle_hook({
        "hook_event_name": "Stop",
        "session_id": session_id,
        "turn_id": turn_id,
        "last_assistant_message": final_msg,
        "transcript_path": str(transcript_file),
        "cwd": str(root),
    }, launch_uploader=False)

    handle_hook({
        "hook_event_name": "SessionEnd",
        "session_id": session_id,
        "transcript_path": str(transcript_file),
        "cwd": str(root),
    }, launch_uploader=False)
    print(f"  Finished in {time.time()-t0:.2f}s! Tokens: {u}")


def run_claude_turn(turn_idx: int, text: str):
    root = Path(r"c:\projects\agentops\doc-summary-agent")
    session_id = f"ses_claude_{uuid.uuid4().hex[:8]}"
    turn_id = f"turn_02{turn_idx}"
    model_name = "databricks-claude-sonnet-4-5"

    print(f"\n[doc-summary-agent] Invoking {model_name}...")
    t0 = time.time()

    handle_hook({
        "hook_event_name": "SessionStart",
        "session_id": session_id,
        "model": model_name,
        "cwd": str(root),
    }, launch_uploader=False)

    handle_hook({
        "hook_event_name": "UserPromptSubmit",
        "session_id": session_id,
        "turn_id": turn_id,
        "prompt": f"다음 문서를 요약하고 핵심 키워드를 추출해줘: {text[:60]}...",
        "model": model_name,
        "cwd": str(root),
    }, launch_uploader=False)

    tool_call_id = f"call_kw_{uuid.uuid4().hex[:8]}"
    handle_hook({
        "hook_event_name": "PreToolUse",
        "session_id": session_id,
        "turn_id": turn_id,
        "tool_name": "keyword_extractor",
        "tool_use_id": tool_call_id,
        "cwd": str(root),
    }, launch_uploader=False)

    words = re.findall(r"\b\w{2,}\b", text)
    top_kws = dict(collections.Counter(words).most_common(5))

    handle_hook({
        "hook_event_name": "PostToolUse",
        "session_id": session_id,
        "turn_id": turn_id,
        "tool_name": "keyword_extractor",
        "tool_use_id": tool_call_id,
        "tool_result": json.dumps(top_kws),
        "cwd": str(root),
    }, launch_uploader=False)

    sub_id = "summary-reviewer"
    handle_hook({
        "hook_event_name": "SubagentStart",
        "session_id": session_id,
        "turn_id": turn_id,
        "agent_id": sub_id,
        "agent_type": "skill-based-subagent",
        "cwd": str(root),
    }, launch_uploader=False)

    prompt = f"문서 검토: 본문에서 추출된 키워드 {list(top_kws.keys())}가 원문의 의미를 잘 포괄하는지 1문장으로 평하세요."
    resp = w.serving_endpoints.query(
        name=model_name,
        messages=[ChatMessage(role=ChatMessageRole.USER, content=prompt)],
        max_tokens=50
    )
    opinion = resp.choices[0].message.content.strip()
    u = resp.usage.as_dict() if resp.usage else {"prompt_tokens": 130, "completion_tokens": 50, "total_tokens": 180}

    handle_hook({
        "hook_event_name": "SubagentStop",
        "session_id": session_id,
        "turn_id": turn_id,
        "agent_id": sub_id,
        "agent_type": "skill-based-subagent",
        "cwd": str(root),
    }, launch_uploader=False)

    transcript_file = root / ".system_generated" / "logs" / "transcript.jsonl"
    transcript_file.parent.mkdir(parents=True, exist_ok=True)
    with transcript_file.open("a", encoding="utf-8") as f:
        rec = {
            "type": "token_usage_record",
            "payload": {
                "session_id": session_id,
                "turn_id": turn_id,
                "timestamp": time.time(),
                "model": model_name,
                "usage": {
                    "input_tokens": u.get("prompt_tokens", 130),
                    "output_tokens": u.get("completion_tokens", 50),
                    "total_tokens": u.get("total_tokens", 180),
                    "cached_input_tokens": 0
                }
            }
        }
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    final_msg = f"도구 추출({top_kws}) 및 서브에이전트 검토({opinion}) 완료."
    handle_hook({
        "hook_event_name": "Stop",
        "session_id": session_id,
        "turn_id": turn_id,
        "last_assistant_message": final_msg,
        "transcript_path": str(transcript_file),
        "cwd": str(root),
    }, launch_uploader=False)

    handle_hook({
        "hook_event_name": "SessionEnd",
        "session_id": session_id,
        "transcript_path": str(transcript_file),
        "cwd": str(root),
    }, launch_uploader=False)
    print(f"  Finished in {time.time()-t0:.2f}s! Tokens: {u}")


print("=== Executing GPT & Claude Real Agent Inferences ===")
run_gpt_turn(1, 4400000)
run_gpt_turn(2, 9900000)
run_claude_turn(1, "엔터프라이즈 환경에서 데이터 거버넌스와 AI 모델 관제는 비즈니스 신뢰성을 확보하는 핵심 축입니다.")
run_claude_turn(2, "멀티 모델 서빙 환경에서 각 프로바이더별 토큰 소비량과 비용을 비교 분석하는 파이프라인이 필수적입니다.")

print("\n=== Exporting to Databricks MLflow UC Tracing ===")
cfg = load_settings()
ob = Outbox(outbox_path())
res = export_pending(ob, cfg)
print(f"Successfully uploaded: {res.uploaded} turns! (Failed: {res.failed})")
