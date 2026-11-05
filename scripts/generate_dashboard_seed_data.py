"""Databricks AI/BI 대시보드 실습을 위한 풍부한 관제 시드 데이터 생성 드라이버.

4종 에이전트(Skill, Code, No-code), 5명의 사용자, 다양한 상태(성공, 실패, 미완료 호출, 미승인 버전 등),
도구 및 서브에이전트 호출, 토큰 소비량, HITL 피드백, 릴리스 게이트 승인 이력을 생성하여
Databricks Unity Catalog Delta Table 및 MLflow Trace로 적재합니다.
"""

from __future__ import annotations

import json
import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from databricks.sdk import WorkspaceClient
from codex_agentops.config import load_settings
from codex_agentops.mlflow_exporter import export_pending
from codex_agentops.outbox import Outbox
from codex_agentops.paths import outbox_path


def main():
    settings = load_settings()
    w = WorkspaceClient(profile=settings.profile)
    wh_id = settings.warehouse_id
    outbox = Outbox(outbox_path())
    
    print("=== [1] 거버넌스 Registry (`agents`, `release_gates`) 시드 데이터 적재 ===")
    
    # 4종 에이전트 정의
    agents = [
        {
            "agent_id": "test-skill-agent",
            "name": "Test Skill Agent",
            "description": "문서 분석 및 검증용 Skill 기반 에이전트",
            "agent_type": "skill-based-agent",
            "agent_version": "1.0.0",
            "build_type": "skill",
            "serving_type": "apps",
            "origin": "databricks",
            "owner": "ino0121@saltware.co.kr",
            "owner_group": "AI-CoE",
            "service_criticality": "중",
            "data_sensitivity": "내부",
            "security_level": "일반",
            "flagship_model": False,
            "model_service": "databricks-meta-llama-3-3-70b-instruct",
            "lifecycle": "production",
            "current_version": "1.0.0",
        },
        {
            "agent_id": "financial-audit-agent",
            "name": "Financial Audit Agent",
            "description": "재무제표 감사 및 외환 계산용 Code 기반 고신뢰 에이전트",
            "agent_type": "agent-bricks-agent",
            "agent_version": "2.1.0",
            "build_type": "code",
            "serving_type": "apps",
            "origin": "databricks",
            "owner": "alice@saltware.co.kr",
            "owner_group": "Finance-Tech",
            "service_criticality": "상",
            "data_sensitivity": "대외비",
            "security_level": "보안",
            "flagship_model": True,
            "model_service": "system.ai.gpt-5-6-sol",
            "lifecycle": "production",
            "current_version": "2.1.0",
        },
        {
            "agent_id": "customer-support-agent",
            "name": "Customer Support Genie",
            "description": "고객 FAQ 검색 및 티켓 접수용 No-code 에이전트",
            "agent_type": "genie-agent",
            "agent_version": "1.2.0",
            "build_type": "no-code",
            "serving_type": "genie",
            "origin": "databricks",
            "owner": "bob@saltware.co.kr",
            "owner_group": "Customer-Success",
            "service_criticality": "하",
            "data_sensitivity": "공개",
            "security_level": "일반",
            "flagship_model": False,
            "model_service": "databricks-meta-llama-3-3-70b-instruct",
            "lifecycle": "production",
            "current_version": "1.2.0",
        },
        {
            "agent_id": "doc-analysis-agent",
            "name": "Document Analysis Agent",
            "description": "대용량 사내 PDF 및 규정 분석 에이전트",
            "agent_type": "skill-based-agent",
            "agent_version": "0.9.0",
            "build_type": "skill",
            "serving_type": "apps",
            "origin": "databricks",
            "owner": "charlie@saltware.co.kr",
            "owner_group": "Data-Platform",
            "service_criticality": "중",
            "data_sensitivity": "내부",
            "security_level": "일반",
            "flagship_model": False,
            "model_service": "databricks-meta-llama-3-3-70b-instruct",
            "lifecycle": "staging",
            "current_version": "0.9.0",
        },
    ]

    for a in agents:
        sql = f"""
        MERGE INTO sk_inno_aops.agentops_test.agents target
        USING (SELECT '{a["agent_id"]}' AS agent_id) source
        ON target.agent_id = source.agent_id
        WHEN MATCHED THEN UPDATE SET
            name = '{a["name"]}', description = '{a["description"]}', agent_type = '{a["agent_type"]}',
            agent_version = '{a["agent_version"]}', build_type = '{a["build_type"]}', serving_type = '{a["serving_type"]}',
            origin = '{a["origin"]}', owner = '{a["owner"]}', owner_group = '{a["owner_group"]}',
            service_criticality = '{a["service_criticality"]}', data_sensitivity = '{a["data_sensitivity"]}',
            security_level = '{a["security_level"]}', flagship_model = {str(a["flagship_model"]).lower()},
            model_service = '{a["model_service"]}', lifecycle = '{a["lifecycle"]}', current_version = '{a["current_version"]}',
            updated_at = current_timestamp()
        WHEN NOT MATCHED THEN INSERT (
            agent_id, name, description, agent_type, agent_version, build_type, serving_type,
            origin, owner, owner_group, service_criticality, data_sensitivity, security_level,
            flagship_model, model_service, lifecycle, current_version, created_at, updated_at
        ) VALUES (
            '{a["agent_id"]}', '{a["name"]}', '{a["description"]}', '{a["agent_type"]}', '{a["agent_version"]}',
            '{a["build_type"]}', '{a["serving_type"]}', '{a["origin"]}', '{a["owner"]}', '{a["owner_group"]}',
            '{a["service_criticality"]}', '{a["data_sensitivity"]}', '{a["security_level"]}',
            {str(a["flagship_model"]).lower()}, '{a["model_service"]}', '{a["lifecycle"]}', '{a["current_version"]}',
            current_timestamp(), current_timestamp()
        )
        """
        w.statement_execution.execute_statement(warehouse_id=wh_id, statement=sql, wait_timeout="30s")
    print(f"  - `agents` 테이블 {len(agents)}개 에이전트 등록 완료")

    # 릴리스 게이트 승인 이력 적재
    gates_sql = """
    MERGE INTO sk_inno_aops.agentops_test.release_gates target
    USING (
        SELECT 'gate-001' AS gate_id, 'test-skill-agent' AS agent_id, '1.0.0' AS version,
               '{\"correctness\": 0.92, \"latency_p90\": 2.8}' AS checks_json, 'approved' AS decision,
               'trace_001' AS evidence_ref, 'admin@saltware.co.kr' AS decided_by,
               current_timestamp() - INTERVAL 5 DAY AS decided_at, 'minor' AS upgrade_type
        UNION ALL
        SELECT 'gate-002', 'financial-audit-agent', '2.0.0', '{\"correctness\": 0.98, \"safety\": 1.0}', 'approved',
               'trace_002', 'compliance@saltware.co.kr', current_timestamp() - INTERVAL 12 DAY, 'major'
        UNION ALL
        SELECT 'gate-003', 'financial-audit-agent', '2.1.0', '{\"correctness\": 0.99, \"safety\": 1.0}', 'approved',
               'trace_003', 'compliance@saltware.co.kr', current_timestamp() - INTERVAL 2 DAY, 'minor'
        UNION ALL
        SELECT 'gate-004', 'customer-support-agent', '1.2.0', '{\"relevance\": 0.95}', 'approved',
               'trace_004', 'support_mgr@saltware.co.kr', current_timestamp() - INTERVAL 8 DAY, 'minor'
        UNION ALL
        SELECT 'gate-005', 'doc-analysis-agent', '0.9.0', '{\"correctness\": 0.72}', 'rejected',
               'trace_005', 'qa@saltware.co.kr', current_timestamp() - INTERVAL 1 DAY, 'patch'
    ) source
    ON target.gate_id = source.gate_id
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
    """
    w.statement_execution.execute_statement(warehouse_id=wh_id, statement=gates_sql, wait_timeout="30s")
    print("  - `release_gates` 테이블 승인/반려 이력 5건 등록 완료")

    print("\n=== [2] 다양한 시나리오 턴(Turn) 생성 및 Outbox 적재 ===")
    
    users = ["ino0121@saltware.co.kr", "alice@saltware.co.kr", "bob@saltware.co.kr", "charlie@saltware.co.kr", "david@saltware.co.kr"]
    scenarios = [
        # (agent_idx, prompt, tool_name, tool_failed, unfinished, subagent_id, in_tok, out_tok, cached_tok, latency_ms, status, revision)
        (0, "신규 사업 보고서 지표 검증 요청", "text_metrics_calculator", False, False, "verifier", 210, 85, 0, 1850, "ok", "1.0.0"),
        (0, "IT 인프라 표준 가이드 요약 분석", "text_metrics_calculator", False, False, "verifier", 450, 120, 128, 2200, "ok", "1.0.0"),
        (0, "미승인 로컬 코드 긴급 실행 테스트", "text_metrics_calculator", False, False, "verifier", 180, 60, 0, 1600, "ok", "working"),
        (1, "2026 Q3 재무제표 손익 계산 검산", "currency_converter", False, False, "audit_checker", 1250, 340, 512, 3400, "ok", "2.1.0"),
        (1, "해외 법인 환율 변동 영향도 시뮬레이션", "tax_auditor", False, False, "audit_checker", 2400, 520, 1024, 4800, "ok", "2.1.0"),
        (1, "분기 법인세 세액공제 한도 초과 계산", "tax_auditor", True, False, "audit_checker", 1800, 95, 0, 2100, "error", "2.1.0"), # 도구 실패
        (2, "사내 VPN 접속 불가 조치 방법 문의", "faq_search", False, False, "sentiment_classifier", 150, 45, 0, 850, "ok", "1.2.0"),
        (2, "출장 경비 정산 기한 및 절차 문의", "faq_search", False, False, "sentiment_classifier", 180, 50, 64, 920, "ok", "1.2.0"),
        (2, "노트북 교체 신청 티켓 자동 생성", "ticket_generator", False, True, "sentiment_classifier", 220, 40, 0, 1100, "ok", "1.2.0"), # 미완료 호출
        (3, "클라우드 아키텍처 보안 가이드라인 추출", "pdf_extractor", False, False, "doc_summarizer", 3100, 650, 2048, 6200, "ok", "0.9.0"), # 고지연 p99
        (3, "데이터 거버넌스 규격 문서 목차 요약", "pdf_extractor", False, False, "doc_summarizer", 1400, 280, 512, 2900, "ok", "0.9.0"),
        (3, "사내 규정 위반 사례 키워드 검색", "pdf_extractor", False, False, "doc_summarizer", 980, 190, 0, 2400, "ok", "0.9.0"),
    ]

    dump_dir = Path("C:/projects/agentops/captured_raw_data/bulk_sim")
    dump_dir.mkdir(parents=True, exist_ok=True)
    
    from codex_agentops.hooks import handle_hook

    created_trace_ids = []
    feedbacks_to_insert = []

    for i, sc in enumerate(scenarios, 1):
        ag = agents[sc[0]]
        prompt_text = sc[1]
        tool_name = sc[2]
        is_tool_failed = sc[3]
        is_unfinished = sc[4]
        subagent_name = sc[5]
        in_tokens = sc[6]
        out_tokens = sc[7]
        cached_tokens = sc[8]
        latency_ms = sc[9]
        status_name = sc[10]
        revision = sc[11]
        user_id = random.choice(users)

        sess_id = f"ses_sim_{uuid.uuid4().hex[:12]}"
        turn_id = f"turn_{i:03d}"
        tool_call_id = f"call_{uuid.uuid4().hex[:10]}"

        # 1. SessionStart
        handle_hook({
            "hook_event_name": "SessionStart",
            "session_id": sess_id,
            "model": ag["model_service"],
            "cwd": "C:/projects/agentops/test-skill-agent",
        }, launch_uploader=False)

        # 2. UserPromptSubmit
        handle_hook({
            "hook_event_name": "UserPromptSubmit",
            "session_id": sess_id,
            "turn_id": turn_id,
            "prompt": prompt_text,
            "model": ag["model_service"],
            "cwd": "C:/projects/agentops/test-skill-agent",
        }, launch_uploader=False)

        # 3. PreToolUse
        handle_hook({
            "hook_event_name": "PreToolUse",
            "session_id": sess_id,
            "turn_id": turn_id,
            "tool_name": tool_name,
            "tool_use_id": tool_call_id,
            "tool_input": {"query": prompt_text},
            "cwd": "C:/projects/agentops/test-skill-agent",
        }, launch_uploader=False)

        # 4. PostToolUse (미완료 호출 시뮬레이션의 경우 PostToolUse 생략)
        if not is_unfinished:
            handle_hook({
                "hook_event_name": "PostToolUse",
                "session_id": sess_id,
                "turn_id": turn_id,
                "tool_name": tool_name,
                "tool_use_id": tool_call_id,
                "tool_response": "오류가 발생했습니다: 타임아웃" if is_tool_failed else "정상 처리 결과 데이터",
                "tool_failed": is_tool_failed,
                "cwd": "C:/projects/agentops/test-skill-agent",
            }, launch_uploader=False)

        # 5. SubagentStart & Stop
        handle_hook({
            "hook_event_name": "SubagentStart",
            "session_id": sess_id,
            "turn_id": turn_id,
            "agent_id": subagent_name,
            "agent_type": "skill-based-subagent",
            "cwd": "C:/projects/agentops/test-skill-agent",
        }, launch_uploader=False)

        handle_hook({
            "hook_event_name": "SubagentStop",
            "session_id": sess_id,
            "turn_id": turn_id,
            "agent_id": subagent_name,
            "agent_type": "skill-based-subagent",
            "last_assistant_message": f"{subagent_name} 서브에이전트 검토 완료",
            "cwd": "C:/projects/agentops/test-skill-agent",
        }, launch_uploader=False)

        # 6. 트랜스크립트 토큰 기록
        t_file = dump_dir / f"{sess_id}_transcript.jsonl"
        with t_file.open("w", encoding="utf-8") as tf:
            tf.write(json.dumps({
                "type": "token_usage_record",
                "payload": {
                    "session_id": sess_id,
                    "thread_id": sess_id,
                    "turn_id": turn_id,
                    "turn_token_usage": {
                        "input_tokens": in_tokens,
                        "output_tokens": out_tokens,
                        "total_tokens": in_tokens + out_tokens,
                        "cached_input_tokens": cached_tokens,
                        "cache_write_input_tokens": 0,
                        "reasoning_output_tokens": 0,
                    },
                },
            }, ensure_ascii=False) + "\n")

        # 7. Stop & SessionEnd
        handle_hook({
            "hook_event_name": "Stop",
            "session_id": sess_id,
            "turn_id": turn_id,
            "last_assistant_message": f"'{prompt_text}'에 대한 답변이 성공적으로 작성되었습니다.",
            "transcript_path": str(t_file),
            "cwd": "C:/projects/agentops/test-skill-agent",
        }, launch_uploader=False)

        handle_hook({
            "hook_event_name": "SessionEnd",
            "session_id": sess_id,
            "transcript_path": str(t_file),
            "cwd": "C:/projects/agentops/test-skill-agent",
        }, launch_uploader=False)

        # outbox 이벤트 레코드의 메타데이터 보정 (에이전트명, 조직명, 리비전, 플래그십 여부 등 덮어쓰기)
        with outbox._connect() as conn:
            # 방금 적재된 해당 세션 이벤트들의 payload 수정
            rows = conn.execute("SELECT event_id, payload FROM outbox_events WHERE session_id = ?", (sess_id,)).fetchall()
            for r in rows:
                p = json.loads(r["payload"])
                p["agent_id"] = ag["agent_id"]
                p["agent_name"] = ag["name"]
                p["agent_type"] = ag["agent_type"]
                p["build_type"] = ag["build_type"]
                p["serving_type"] = ag["serving_type"]
                p["owner"] = ag["owner"]
                p["owner_group"] = ag["owner_group"]
                p["model_service"] = ag["model_service"]
                p["model"] = ag["model_service"]
                p["flagship_model"] = ag["flagship_model"]
                p["release_version"] = revision
                p["user_name"] = user_id
                p["security_level"] = ag["security_level"]
                p["data_sensitivity"] = ag["data_sensitivity"]
                conn.execute("UPDATE outbox_events SET payload = ? WHERE event_id = ?", (json.dumps(p, ensure_ascii=False), r["event_id"]))
            conn.execute("UPDATE turn_uploads SET agent_id = ? WHERE session_id = ?", (ag["agent_id"], sess_id))
            conn.commit()

        print(f"  [{i:02d}/12] 세션 {sess_id} 적재: Agent={ag['agent_id']}, User={user_id}, Tool={tool_name}, Status={status_name}")

    print("\n=== [3] Outbox의 전체 턴을 Databricks MLflow Trace로 업로드 ===")
    
    with outbox._connect() as conn:
        conn.execute("UPDATE turn_uploads SET status = 'pending', lease_until_ns = 0")
        conn.commit()

    uploaded_count = 0
    while True:
        res = export_pending(outbox, settings, limit=5, require_usage=False)
        if res.uploaded == 0:
            break
        uploaded_count += res.uploaded
        created_trace_ids.extend(res.trace_ids)
        print(f"  - 중간 업로드 완료: {res.uploaded}건 (누적: {uploaded_count}건)")
        time.sleep(1)

    print(f"\n총 {uploaded_count}건의 Trace가 Databricks MLflow Experiment에 적재되었습니다.")

    print("\n=== [4] Review App HITL 피드백 데이터 생성 ===")
    # 업로드된 Trace ID들에 대해 전문가 평가 피드백 삽입
    for idx, tid in enumerate(created_trace_ids[:8], 1):
        clean_tid = tid.split("/")[-1]
        is_corr = (idx % 7 != 0)  # 간헐적 오답 생성
        rating = 5 if is_corr else 2
        comment = "정확하고 완결성 높은 답변" if is_corr else "일부 세부 계산 불일치 감지"
        ag_id = agents[idx % len(agents)]["agent_id"]
        feedbacks_to_insert.append(
            f"('fb-{idx:03d}', '{clean_tid}', '{ag_id}', 'expert_{idx%3+1}@saltware.co.kr', {str(is_corr).lower()}, {rating}, '{comment}', current_timestamp() - INTERVAL {idx} HOUR)"
        )

    if feedbacks_to_insert:
        feedbacks_sql = f"""
        INSERT INTO sk_inno_aops.agentops_test.review_app_feedbacks
        (feedback_id, trace_id, agent_id, reviewer, is_correct, rating, comment, created_at)
        VALUES {', '.join(feedbacks_to_insert)}
        """
        w.statement_execution.execute_statement(warehouse_id=wh_id, statement=feedbacks_sql, wait_timeout="30s")
        print(f"  - `review_app_feedbacks` 테이블 {len(feedbacks_to_insert)}건 적재 완료")

    print("\n모든 대시보드 시드 데이터 생성이 성공적으로 완료되었습니다!")


if __name__ == "__main__":
    main()

