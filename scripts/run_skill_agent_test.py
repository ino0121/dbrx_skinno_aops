"""Skill-based 에이전트 E2E 테스트 및 텔레메트리 파이프라인 수집 드라이버.

이 스크립트는 Databricks Foundation Model Serving(Llama 3.3 70B)을 실제로 호출하고,
도구(Tool) 1회 실행 및 서브에이전트(Subagent) 1회 위임을 수행하여
Codex Hook 표준 규격의 Raw 이벤트를 Outbox에 적재한 뒤 Databricks MLflow Trace로 전송합니다.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

# UTF-8 출력 보장
sys.stdout.reconfigure(encoding="utf-8")

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

from codex_agentops.config import load_settings
from codex_agentops.hooks import handle_hook
from codex_agentops.mlflow_exporter import export_pending
from codex_agentops.outbox import Outbox
from codex_agentops.paths import outbox_path


def calculate_text_metrics(text: str) -> dict[str, int]:
    """간단한 텍스트 지표 계산 도구 (Tool)."""
    words = text.split()
    chars_with_spaces = len(text)
    chars_no_spaces = len(text.replace(" ", ""))
    sentences = [s for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    return {
        "word_count": len(words),
        "char_count": chars_with_spaces,
        "char_count_no_spaces": chars_no_spaces,
        "sentence_count": len(sentences),
    }


def main():
    root = Path("C:/projects/agentops/test-skill-agent").resolve()
    settings = load_settings()
    outbox = Outbox(outbox_path())
    w = WorkspaceClient(profile=settings.profile)
    model_name = "databricks-meta-llama-3-3-70b-instruct"

    session_id = f"ses_{uuid.uuid4().hex[:16]}"
    turn_id = "turn_001"
    user_query = "AgentOps는 AI 에이전트의 품질, 안정성, 비용 및 거버넌스를 관제하는 통합 운영 플랫폼입니다."
    
    # 캡처 파일 디렉토리 준비
    dump_dir = Path("C:/projects/agentops/captured_raw_data")
    dump_dir.mkdir(parents=True, exist_ok=True)
    raw_events: list[dict] = []

    print(f"=== [1] 세션 및 턴 시작 (Session: {session_id}, Turn: {turn_id}) ===")
    
    # 1. SessionStart Hook
    ev_session_start = {
        "hook_event_name": "SessionStart",
        "session_id": session_id,
        "model": model_name,
        "cwd": str(root),
    }
    raw_events.append(ev_session_start)
    handle_hook(ev_session_start, launch_uploader=False)

    # 2. UserPromptSubmit Hook
    ev_user_prompt = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": session_id,
        "turn_id": turn_id,
        "prompt": f"다음 텍스트의 지표를 산출하고 verifier로 검증하라: '{user_query}'",
        "model": model_name,
        "cwd": str(root),
    }
    raw_events.append(ev_user_prompt)
    handle_hook(ev_user_prompt, launch_uploader=False)

    # 3. Tool 실행: text_metrics_calculator
    tool_use_id = f"call_{uuid.uuid4().hex[:12]}"
    tool_input = {"text": user_query}
    print(f"=== [2] Tool 실행: text_metrics_calculator (ID: {tool_use_id}) ===")
    
    ev_pre_tool = {
        "hook_event_name": "PreToolUse",
        "session_id": session_id,
        "turn_id": turn_id,
        "tool_name": "text_metrics_calculator",
        "tool_use_id": tool_use_id,
        "tool_input": tool_input,
        "cwd": str(root),
    }
    raw_events.append(ev_pre_tool)
    handle_hook(ev_pre_tool, launch_uploader=False)

    t0 = time.perf_counter()
    tool_output = calculate_text_metrics(user_query)
    duration_ms = (time.perf_counter() - t0) * 1000.0
    time.sleep(0.05)  # 최소 지연 보장

    ev_post_tool = {
        "hook_event_name": "PostToolUse",
        "session_id": session_id,
        "turn_id": turn_id,
        "tool_name": "text_metrics_calculator",
        "tool_use_id": tool_use_id,
        "tool_response": json.dumps(tool_output, ensure_ascii=False),
        "tool_failed": False,
        "cwd": str(root),
    }
    raw_events.append(ev_post_tool)
    handle_hook(ev_post_tool, launch_uploader=False)
    print(f"Tool 결과: {tool_output} (소요시간: {duration_ms:.2f}ms)")

    # 4. Subagent 위임: verifier (Databricks Model Serving 실제 호출)
    subagent_id = "verifier"
    print(f"=== [3] Subagent 위임: {subagent_id} (실제 Databricks LLM 추론) ===")
    
    ev_subagent_start = {
        "hook_event_name": "SubagentStart",
        "session_id": session_id,
        "turn_id": turn_id,
        "agent_id": subagent_id,
        "agent_type": "skill-based-subagent",
        "cwd": str(root),
    }
    raw_events.append(ev_subagent_start)
    handle_hook(ev_subagent_start, launch_uploader=False)

    # 실제 Databricks Model Serving 호출
    system_prompt = (
        "당신은 verifier 서브에이전트입니다. 전달받은 원문 텍스트와 도구 산출 지표를 확인하고, "
        "단어 수와 글자 수 등의 정합성을 검증한 판정 결과를 1~2문장으로 한국어로 답변하세요."
    )
    user_msg = f"원문: {user_query}\n도구 산출 지표: {json.dumps(tool_output, ensure_ascii=False)}"
    
    resp = w.serving_endpoints.query(
        name=model_name,
        messages=[
            ChatMessage(role=ChatMessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=ChatMessageRole.USER, content=user_msg),
        ],
        max_tokens=150,
    )
    subagent_text = resp.choices[0].message.content.strip()
    usage = resp.usage
    print(f"Subagent 답변: {subagent_text}")
    print(f"실제 소비 토큰: Prompt={usage.prompt_tokens}, Completion={usage.completion_tokens}, Total={usage.total_tokens}")

    ev_subagent_stop = {
        "hook_event_name": "SubagentStop",
        "session_id": session_id,
        "turn_id": turn_id,
        "agent_id": subagent_id,
        "agent_type": "skill-based-subagent",
        "last_assistant_message": subagent_text,
        "cwd": str(root),
    }
    raw_events.append(ev_subagent_stop)
    handle_hook(ev_subagent_stop, launch_uploader=False)

    # 5. 세션 트랜스크립트 파일에 토큰 기록 작성
    transcript_file = dump_dir / f"{session_id}_transcript.jsonl"
    token_record = {
        "type": "token_usage_record",
        "payload": {
            "session_id": session_id,
            "thread_id": session_id,
            "turn_id": turn_id,
            "turn_token_usage": {
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "reasoning_output_tokens": 0,
            },
        },
    }
    with transcript_file.open("w", encoding="utf-8") as f:
        f.write(json.dumps(token_record, ensure_ascii=False) + "\n")

    # 6. Stop & SessionEnd Hook
    final_answer = f"텍스트 분석 지표({tool_output})가 산출되었으며, verifier 서브에이전트 검증 결과({subagent_text})를 확인했습니다."
    ev_stop = {
        "hook_event_name": "Stop",
        "session_id": session_id,
        "turn_id": turn_id,
        "last_assistant_message": final_answer,
        "transcript_path": str(transcript_file),
        "cwd": str(root),
    }
    raw_events.append(ev_stop)
    handle_hook(ev_stop, launch_uploader=False)

    ev_session_end = {
        "hook_event_name": "SessionEnd",
        "session_id": session_id,
        "transcript_path": str(transcript_file),
        "cwd": str(root),
    }
    raw_events.append(ev_session_end)
    handle_hook(ev_session_end, launch_uploader=False)

    # Raw 이벤트 전체 덤프 파일 저장
    raw_events_path = dump_dir / f"{session_id}_raw_hook_events.json"
    with raw_events_path.open("w", encoding="utf-8") as f:
        json.dump(raw_events, f, ensure_ascii=False, indent=2)
    print(f"\n[Raw Data 덤프 완료]")
    print(f"  - Stdin Hook 이벤트 원본: {raw_events_path}")
    print(f"  - 세션 트랜스크립트 로그: {transcript_file}")

    # 7. Databricks MLflow Trace 업로드
    print("\n=== [4] Databricks MLflow Trace 업로드 (export_pending) ===")
    export_result = export_pending(outbox, settings, limit=10, require_usage=True)
    print(f"MLflow 업로드 결과: uploaded={export_result.uploaded}, failed={export_result.failed}")
    print(f"생성된 Trace ID: {export_result.trace_ids}")

    trace_id = export_result.trace_ids[0] if export_result.trace_ids else None
    if trace_id:
        print(f"\n성공! Databricks MLflow Trace가 생성되었습니다.")
        print(f"Trace ID: {trace_id}")
        return session_id, trace_id, str(raw_events_path), str(transcript_file)
    else:
        print("경고: 업로드된 Trace ID가 없습니다.")
        return session_id, None, str(raw_events_path), str(transcript_file)


if __name__ == "__main__":
    main()

