"""3종 Skill-based 에이전트 대상 실제 도구 실행 및 실제 Databricks LLM 추론 쿼리 드라이버.

각 에이전트에 대해 실제 도구 함수(단어분석, VAT계산, 키워드추출)를 실행하고,
Databricks Foundation Model Serving(Llama 3.3 70B)에 실시간 네트워크 요청을 보내
실제 응답 텍스트와 실제 소비 토큰을 수집한 뒤,
Codex Hook 수명주기 텔레메트리를 통해 Databricks MLflow Tracing으로 업로드합니다.
"""

from __future__ import annotations

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


# __________ [실제 도구 함수들] __________

def text_metrics_calculator(text: str) -> dict[str, int]:
    """실제 단어, 문자, 문장 수 분석 도구."""
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


def vat_calculator(total_amount: int) -> dict[str, int]:
    """실제 거래 총액 기반 공급가액 및 부가세 10% 계산 도구."""
    supply_amount = int(round(total_amount / 1.1))
    vat = total_amount - supply_amount
    return {
        "total_amount": total_amount,
        "supply_amount": supply_amount,
        "vat": vat,
    }


def keyword_extractor(text: str) -> dict[str, int]:
    """실제 주요 단어 빈도 추출 도구."""
    tokens = re.findall(r"[가-힣A-Za-z0-9_]{2,}", text)
    stopwords = {"에서", "대한", "위해", "통해", "으로", "하는", "있습니다", "하고", "이며"}
    filtered = [t for t in tokens if t not in stopwords]
    counter = collections.Counter(filtered)
    return dict(counter.most_common(5))


# __________ [실행 시나리오 목록] __________

REAL_RUN_SCENARIOS = [
    # [Agent 1: test-skill-agent]
    {
        "agent_dir": "test-skill-agent",
        "agent_id": "test-skill-agent",
        "user_query": "Databricks Unity Catalog는 데이터와 AI 자산에 대한 통합 거버넌스를 제공합니다.",
        "tool_name": "text_metrics_calculator",
        "tool_fn": lambda: text_metrics_calculator("Databricks Unity Catalog는 데이터와 AI 자산에 대한 통합 거버넌스를 제공합니다."),
        "subagent_id": "verifier",
        "subagent_prompt": "당신은 verifier 서브에이전트입니다. 원문과 도구 분석 지표의 단어/글자 수가 맞는지 검증하여 1문장으로 한국어로 답변하세요.",
    },
    {
        "agent_dir": "test-skill-agent",
        "agent_id": "test-skill-agent",
        "user_query": "Delta Lake는 ACID 트랜잭션과 확장 가능한 메타데이터 처리를 지원하는 오픈 소스 스토리지 프레임워크입니다.",
        "tool_name": "text_metrics_calculator",
        "tool_fn": lambda: text_metrics_calculator("Delta Lake는 ACID 트랜잭션과 확장 가능한 메타데이터 처리를 지원하는 오픈 소스 스토리지 프레임워크입니다."),
        "subagent_id": "verifier",
        "subagent_prompt": "당신은 verifier 서브에이전트입니다. 도구 산출 지표와 원문을 검토하여 정상 여부를 1문장으로 한국어로 보고하세요.",
    },
    # [Agent 2: financial-calculator-agent]
    {
        "agent_dir": "financial-calculator-agent",
        "agent_id": "financial-calculator-agent",
        "user_query": "총 거래 금액 55,000,000원에 대해 공급가액과 부가세를 산출하고 tax-auditor를 통해 세무 감사를 수행해주세요.",
        "tool_name": "vat_calculator",
        "tool_fn": lambda: vat_calculator(55000000),
        "subagent_id": "tax-auditor",
        "subagent_prompt": "당신은 tax-auditor 서브에이전트입니다. 산출된 공급가액과 부가세(10%) 계산이 세법 기준에 정확히 부합하는지 1문장으로 한국어로 감사 결과를 작성하세요.",
    },
    {
        "agent_dir": "financial-calculator-agent",
        "agent_id": "financial-calculator-agent",
        "user_query": "총 거래 금액 13,200,000원에 대한 부가세 산출 및 세액 정합성을 검토해주세요.",
        "tool_name": "vat_calculator",
        "tool_fn": lambda: vat_calculator(13200000),
        "subagent_id": "tax-auditor",
        "subagent_prompt": "당신은 tax-auditor 서브에이전트입니다. 공급가액과 부가세의 합이 총액과 일치하는지 확인하고 1문장으로 한국어로 답변하세요.",
    },
    # [Agent 3: doc-summary-agent]
    {
        "agent_dir": "doc-summary-agent",
        "agent_id": "doc-summary-agent",
        "user_query": "머신러닝 파이프라인에서 모델 서빙과 모니터링은 필수적이며, 모델 드리프트와 데이터 품질을 지속적으로 추적해야 합니다.",
        "tool_name": "keyword_extractor",
        "tool_fn": lambda: keyword_extractor("머신러닝 파이프라인에서 모델 서빙과 모니터링은 필수적이며, 모델 드리프트와 데이터 품질을 지속적으로 추적해야 합니다."),
        "subagent_id": "summary-reviewer",
        "subagent_prompt": "당신은 summary-reviewer 서브에이전트입니다. 추출된 주요 키워드가 원문의 핵심 주제를 적절히 대표하는지 1문장으로 한국어로 평가하세요.",
    },
    {
        "agent_dir": "doc-summary-agent",
        "agent_id": "doc-summary-agent",
        "user_query": "클라우드 데이터 웨어하우스 환경에서 서버리스 컴퓨팅은 비용 최적화와 탄력적 리소스 확장을 가능하게 합니다.",
        "tool_name": "keyword_extractor",
        "tool_fn": lambda: keyword_extractor("클라우드 데이터 웨어하우스 환경에서 서버리스 컴퓨팅은 비용 최적화와 탄력적 리소스 확장을 가능하게 합니다."),
        "subagent_id": "summary-reviewer",
        "subagent_prompt": "당신은 summary-reviewer 서브에이전트입니다. 추출된 키워드와 원문 주제의 부합성을 1문장으로 한국어로 검토하세요.",
    },
]


def execute_turn(scenario: dict, index: int, settings, w: WorkspaceClient, outbox: Outbox) -> str:
    root = Path(f"C:/projects/agentops/{scenario['agent_dir']}").resolve()
    model_name = "databricks-meta-llama-3-3-70b-instruct"
    session_id = f"ses_{uuid.uuid4().hex[:12]}"
    turn_id = f"turn_{index:03d}"
    dump_dir = Path("C:/projects/agentops/captured_raw_data/real_runs")
    dump_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[{index}/{len(REAL_RUN_SCENARIOS)}] 에이전트 실행 시작: {scenario['agent_id']}")
    print(f"  질의: {scenario['user_query']}")

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
        "prompt": scenario["user_query"],
        "model": model_name,
        "cwd": str(root),
    }, launch_uploader=False)

    # 3. 실제 도구 실행
    tool_call_id = f"call_{uuid.uuid4().hex[:10]}"
    handle_hook({
        "hook_event_name": "PreToolUse",
        "session_id": session_id,
        "turn_id": turn_id,
        "tool_name": scenario["tool_name"],
        "tool_use_id": tool_call_id,
        "tool_input": {"input": scenario["user_query"]},
        "cwd": str(root),
    }, launch_uploader=False)

    t0 = time.perf_counter()
    tool_res = scenario["tool_fn"]()
    tool_duration_ms = (time.perf_counter() - t0) * 1000.0
    print(f"  실제 도구 결과: {tool_res} (소요: {tool_duration_ms:.2f}ms)")

    handle_hook({
        "hook_event_name": "PostToolUse",
        "session_id": session_id,
        "turn_id": turn_id,
        "tool_name": scenario["tool_name"],
        "tool_use_id": tool_call_id,
        "tool_response": json.dumps(tool_res, ensure_ascii=False),
        "tool_failed": False,
        "cwd": str(root),
    }, launch_uploader=False)

    # 4. 서브에이전트 위임 및 실제 Databricks Model Serving 네트워크 호출
    subagent_id = scenario["subagent_id"]
    handle_hook({
        "hook_event_name": "SubagentStart",
        "session_id": session_id,
        "turn_id": turn_id,
        "agent_id": subagent_id,
        "agent_type": "skill-based-subagent",
        "cwd": str(root),
    }, launch_uploader=False)

    print(f"  실제 LLM 호출 중 ({model_name})...")
    llm_user_msg = f"원문: {scenario['user_query']}\n도구 결과: {json.dumps(tool_res, ensure_ascii=False)}"
    resp = w.serving_endpoints.query(
        name=model_name,
        messages=[
            ChatMessage(role=ChatMessageRole.SYSTEM, content=scenario["subagent_prompt"]),
            ChatMessage(role=ChatMessageRole.USER, content=llm_user_msg),
        ],
        max_tokens=150,
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
    final_output = f"도구 실행 결과({tool_res})와 서브에이전트 검토({subagent_reply})가 완료되었습니다."
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

    return session_id


def main():
    settings = load_settings()
    w = WorkspaceClient(profile=settings.profile)
    outbox = Outbox(outbox_path())

    print("=== [실제 3종 에이전트 E2E 쿼리 실행 시작] ===")
    session_ids = []
    for i, sc in enumerate(REAL_RUN_SCENARIOS, 1):
        sid = execute_turn(sc, i, settings, w, outbox)
        session_ids.append(sid)
        time.sleep(0.5)

    print(f"\n총 {len(session_ids)}개의 세션 및 턴이 로컬 Outbox에 실제 생성되었습니다.")
    
    # MLflow Trace로 업로드
    print("\n=== [Databricks MLflow Trace로 실시간 전송] ===")
    with outbox._connect() as conn:
        conn.execute("UPDATE turn_uploads SET status = 'pending', lease_until_ns = 0")
        conn.commit()

    uploaded_total = 0
    all_trace_ids = []
    for attempt in range(10):
        res = export_pending(outbox, settings, limit=5, require_usage=False)
        if res.uploaded == 0:
            break
        uploaded_total += res.uploaded
        all_trace_ids.extend(res.trace_ids)
        print(f"  - 중간 업로드 완료: {res.uploaded}건 (누적: {uploaded_total}건)")
        time.sleep(1)

    print(f"\n최종 완료! 총 {uploaded_total}건의 실제 실행 Trace가 Databricks MLflow에 성공적으로 적재되었습니다.")
    print("생성된 Trace 목록:")
    for tid in all_trace_ids:
        print(f"  - {tid}")


if __name__ == "__main__":
    main()

