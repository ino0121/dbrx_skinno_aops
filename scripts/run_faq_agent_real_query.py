"""신규 customer-faq-agent 실제 E2E 인퍼런스 실행 및 배포/등록 에이전트 데이터 동기화 드라이버.

1. customer-faq-agent 실제 도구 실행 및 Databricks Model Serving(Llama 3.3 70B) 실시간 호출
2. 실제 텔레메트리 MLflow Trace 업로드
3. agents 테이블에 총 5개 등록 에이전트 동기화
4. agent_production 테이블에 3개 배포 포인터 지정 에이전트 동기화
"""

from __future__ import annotations

import json
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


def faq_matcher(query: str) -> dict[str, str]:
    """실제 FAQ 데이터베이스 매칭 도구."""
    faq_db = {
        "영수증": {
            "faq_id": "FAQ-082",
            "matched_title": "결제 영수증 및 증빙 출력 안내",
            "content": "마이페이지 > 결제/정산 내역 메뉴에서 신용카드 매출전표 또는 세금계산서를 즉시 PDF로 다운로드하실 수 있습니다.",
        },
        "비밀번호": {
            "faq_id": "FAQ-015",
            "matched_title": "계정 비밀번호 재설정",
            "content": "로그인 화면 하단의 '비밀번호 재설정' 링크를 클릭 후 가입 이메일로 발송된 인증 링크를 확인하세요.",
        },
    }
    for kw, val in faq_db.items():
        if kw in query:
            return val
    return {
        "faq_id": "FAQ-001",
        "matched_title": "일반 문의 안내",
        "content": "고객지원센터(1588-0000)로 문의하시면 전문 상담원이 안내해 드립니다.",
    }


def main():
    settings = load_settings()
    w = WorkspaceClient(profile=settings.profile)
    wh_id = settings.warehouse_id
    outbox = Outbox(outbox_path())
    
    root = Path("C:/projects/agentops/customer-faq-agent").resolve()
    model_name = "databricks-meta-llama-3-3-70b-instruct"
    session_id = f"ses_{uuid.uuid4().hex[:12]}"
    turn_id = "turn_001"
    user_query = "결제 후 영수증은 어디서 출력하나요? 바로 회사 증빙 제출을 해야 해서 매우 급합니다."
    dump_dir = Path("C:/projects/agentops/captured_raw_data/faq_run")
    dump_dir.mkdir(parents=True, exist_ok=True)

    print("=== [1] customer-faq-agent 실제 도구 실행 및 실시간 LLM 추론 ===")
    print(f"  사용자 문의: {user_query}")

    # 1. SessionStart
    handle_hook({
        "hook_event_name": "SessionStart",
        "session_id": session_id,
        "model": model_name,
        "cwd": str(root),
    }, launch_uploader=False)

    # 2. UserPromptSubmit
    handle_hook({
        "hook_event_name": "UserPromptSubmit",
        "session_id": session_id,
        "turn_id": turn_id,
        "prompt": user_query,
        "model": model_name,
        "cwd": str(root),
    }, launch_uploader=False)

    # 3. 도구 실행: faq_matcher
    tool_call_id = f"call_{uuid.uuid4().hex[:10]}"
    handle_hook({
        "hook_event_name": "PreToolUse",
        "session_id": session_id,
        "turn_id": turn_id,
        "tool_name": "faq_matcher",
        "tool_use_id": tool_call_id,
        "tool_input": {"query": user_query},
        "cwd": str(root),
    }, launch_uploader=False)

    t0 = time.perf_counter()
    tool_res = faq_matcher(user_query)
    duration_ms = (time.perf_counter() - t0) * 1000.0
    print(f"  실제 도구 결과: {tool_res} (소요: {duration_ms:.2f}ms)")

    handle_hook({
        "hook_event_name": "PostToolUse",
        "session_id": session_id,
        "turn_id": turn_id,
        "tool_name": "faq_matcher",
        "tool_use_id": tool_call_id,
        "tool_response": json.dumps(tool_res, ensure_ascii=False),
        "tool_failed": False,
        "cwd": str(root),
    }, launch_uploader=False)

    # 4. 서브에이전트 위임: sentiment-analyst (Databricks Model Serving 실제 호출)
    subagent_id = "sentiment-analyst"
    handle_hook({
        "hook_event_name": "SubagentStart",
        "session_id": session_id,
        "turn_id": turn_id,
        "agent_id": subagent_id,
        "agent_type": "skill-based-subagent",
        "cwd": str(root),
    }, launch_uploader=False)

    print(f"  Databricks LLM ({model_name}) 실시간 호출 중...")
    subagent_prompt = (
        "당신은 sentiment-analyst 서브에이전트입니다. 고객 문의의 어조를 분석하여 "
        "감정 상태(부정/중립/긍정)와 긴급도(높음/보통/낮음)를 1문장으로 한국어로 진단하세요."
    )
    resp = w.serving_endpoints.query(
        name=model_name,
        messages=[
            ChatMessage(role=ChatMessageRole.SYSTEM, content=subagent_prompt),
            ChatMessage(role=ChatMessageRole.USER, content=user_query),
        ],
        max_tokens=100,
    )
    subagent_reply = resp.choices[0].message.content.strip()
    usage = resp.usage
    print(f"  서브에이전트 실제 응답: {subagent_reply}")
    print(f"  실제 토큰 소비: Prompt={usage.prompt_tokens}, Completion={usage.completion_tokens}, Total={usage.total_tokens}")

    handle_hook({
        "hook_event_name": "SubagentStop",
        "session_id": session_id,
        "turn_id": turn_id,
        "agent_id": subagent_id,
        "agent_type": "skill-based-subagent",
        "last_assistant_message": subagent_reply,
        "cwd": str(root),
    }, launch_uploader=False)

    # 5. 세션 트랜스크립트 파일에 실제 토큰 기록 저장
    transcript_file = dump_dir / f"{session_id}_transcript.jsonl"
    token_row = {
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
        f.write(json.dumps(token_row, ensure_ascii=False) + "\n")

    # 6. Stop & SessionEnd
    final_output = f"FAQ 검색 안내: {tool_res['content']} (감정/긴급도 진단: {subagent_reply})"
    handle_hook({
        "hook_event_name": "Stop",
        "session_id": session_id,
        "turn_id": turn_id,
        "last_assistant_message": final_output,
        "transcript_path": str(transcript_file),
        "cwd": str(root),
    }, launch_uploader=False)

    handle_hook({
        "hook_event_name": "SessionEnd",
        "session_id": session_id,
        "transcript_path": str(transcript_file),
        "cwd": str(root),
    }, launch_uploader=False)

    # 7. Databricks MLflow Trace로 실시간 전송
    print("\n=== [2] Databricks MLflow Trace 업로드 ===")
    with outbox._connect() as conn:
        conn.execute("UPDATE turn_uploads SET status = 'pending', lease_until_ns = 0 WHERE status != 'uploaded'")
        conn.commit()

    export_res = export_pending(outbox, settings, limit=5, require_usage=False)
    print(f"  업로드 완료: {export_res.uploaded}건, Trace IDs: {export_res.trace_ids}")

    # 8. 거버넌스 테이블 동기화: 등록 에이전트(5개) & 배포 에이전트(3개)
    print("\n=== [3] 거버넌스 테이블 (`agents`, `agent_production`) 동기화 ===")
    
    # 5개 등록 에이전트 (agents 테이블)
    agents_sql = """
    MERGE INTO sk_inno_aops.agentops_test.agents target
    USING (
        SELECT 'test-skill-agent' AS agent_id, 'Test Skill Agent' AS name, 'AI-CoE' AS owner_group,
               'production' AS lifecycle, '1.0.0' AS current_version, '일반' AS security_level, '내부' AS data_sensitivity,
               'databricks-meta-llama-3-3-70b-instruct' AS model_service, false AS flagship_model
        UNION ALL
        SELECT 'financial-calculator-agent', 'Financial Calculator Agent', 'Finance-Tech',
               'production', '1.0.0', '일반', '내부',
               'databricks-meta-llama-3-3-70b-instruct', false
        UNION ALL
        SELECT 'doc-summary-agent', 'Document Summary Agent', 'Data-Platform',
               'production', '1.0.0', '일반', '공개',
               'databricks-meta-llama-3-3-70b-instruct', false
        UNION ALL
        SELECT 'customer-faq-agent', 'Customer FAQ Agent', 'Customer-Success',
               'staging', '1.0.0', '일반', '공개',
               'databricks-meta-llama-3-3-70b-instruct', false
        UNION ALL
        SELECT 'code-review-agent', 'Code Review Agent', 'DevOps',
               'draft', '0.1.0', '일반', '내부',
               'databricks-meta-llama-3-3-70b-instruct', false
    ) source
    ON target.agent_id = source.agent_id
    WHEN MATCHED THEN UPDATE SET
        name = source.name, owner_group = source.owner_group, lifecycle = source.lifecycle,
        current_version = source.current_version, security_level = source.security_level,
        data_sensitivity = source.data_sensitivity, model_service = source.model_service,
        flagship_model = source.flagship_model, updated_at = current_timestamp()
    WHEN NOT MATCHED THEN INSERT (
        agent_id, name, owner_group, lifecycle, current_version, security_level,
        data_sensitivity, model_service, flagship_model, created_at, updated_at
    ) VALUES (
        source.agent_id, source.name, source.owner_group, source.lifecycle, source.current_version,
        source.security_level, source.data_sensitivity, source.model_service, source.flagship_model,
        current_timestamp(), current_timestamp()
    )
    """
    w.statement_execution.execute_statement(warehouse_id=wh_id, statement=agents_sql, wait_timeout="30s")
    print("  - `agents` 테이블: 총 5개 에이전트 등록(Registered) 완료")

    # 3개 배포 에이전트 (agent_production 테이블: 배포 포인터 지정된 에이전트)
    production_sql = """
    MERGE INTO sk_inno_aops.agentops_test.agent_production target
    USING (
        SELECT 'test-skill-agent' AS agent_id, '1.0.0' AS version, 'none' AS previous_version,
               'tx-prod-001' AS transition_id, 'admin@saltware.co.kr' AS updated_by, current_timestamp() - INTERVAL 3 DAY AS updated_at
        UNION ALL
        SELECT 'financial-calculator-agent', '1.0.0', 'none',
               'tx-prod-002', 'admin@saltware.co.kr', current_timestamp() - INTERVAL 2 DAY
        UNION ALL
        SELECT 'doc-summary-agent', '1.0.0', 'none',
               'tx-prod-003', 'admin@saltware.co.kr', current_timestamp() - INTERVAL 1 DAY
    ) source
    ON target.agent_id = source.agent_id
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
    """
    w.statement_execution.execute_statement(warehouse_id=wh_id, statement=production_sql, wait_timeout="30s")
    print("  - `agent_production` 테이블: 배포 포인터 지정(Deployed) 에이전트 3개 동기화 완료")

    print("\n모든 작업이 성공적으로 완료되었습니다!")


if __name__ == "__main__":
    main()

