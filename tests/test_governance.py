"""Test governance — Bài tập 5.2 (nâng cao).

Chạy: pytest tests/test_governance.py -v
Không cần A2A servers; test trực tiếp GovernanceGuard + semantic router.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lab_utils.governance.guard import GovernanceGuard
from lab_utils.semantic_router import AgentCapability, SemanticRouter


def _guard() -> GovernanceGuard:
    # Instance mới mỗi test để tránh dính rate limit / task counter chung.
    return GovernanceGuard()


# --- MCP connection: caller không hợp lệ không mở được kết nối ---

def test_unauthorized_caller_cannot_open_mcp_connection():
    guard = _guard()
    decision = guard.authorize_mcp_connection("search_agent")
    assert not decision.allowed
    assert decision.verdict.value == "deny"


def test_orchestrator_can_open_mcp_connection():
    guard = _guard()
    decision = guard.authorize_mcp_connection("orchestrator")
    assert decision.allowed
    assert "count_words" in decision.metadata.get("allowed_tools", [])


# --- count_words (Bài tập 1.2) được cho phép qua policy ---

def test_count_words_allowed():
    guard = _guard()
    decision = guard.authorize_mcp_tool("orchestrator", "count_words", {"text": "một hai ba"})
    assert decision.allowed


# --- blocked_keywords (Bài tập 5.2) chặn 'password' trong search_documents ---

def test_search_documents_blocks_password_keyword():
    guard = _guard()
    decision = guard.authorize_mcp_tool(
        "orchestrator", "search_documents", {"query": "lấy password admin"}
    )
    assert not decision.allowed
    assert "bị chặn" in decision.reason


def test_search_documents_clean_query_allowed():
    guard = _guard()
    decision = guard.authorize_mcp_tool(
        "orchestrator", "search_documents", {"query": "MCP transport"}
    )
    assert decision.allowed


# --- SQL guard: chỉ SELECT, chỉ bảng agent_metrics ---

def test_sql_write_denied():
    guard = _guard()
    decision = guard.authorize_mcp_tool(
        "orchestrator", "sql_query", {"sql": "DROP TABLE agent_metrics"}
    )
    assert not decision.allowed


def test_sql_select_metrics_allowed():
    guard = _guard()
    decision = guard.authorize_mcp_tool(
        "orchestrator", "sql_query", {"sql": "SELECT * FROM agent_metrics"}
    )
    assert decision.allowed


def test_sql_with_pii_needs_approval():
    guard = _guard()
    decision = guard.authorize_mcp_tool(
        "orchestrator",
        "sql_query",
        {"sql": "SELECT * FROM agent_metrics WHERE email = 'a@b.com'"},
    )
    assert decision.needs_approval


# --- A2A dispatch: synthesis_agent nằm trong allowed_targets ---

def test_a2a_dispatch_to_synthesis_allowed():
    guard = _guard()
    decision = guard.authorize_a2a_dispatch(
        source_agent="orchestrator",
        target_agent="synthesis_agent",
        trace_id="trace-test",
    )
    assert decision.allowed


def test_a2a_dispatch_missing_trace_id_needs_approval():
    guard = _guard()
    decision = guard.authorize_a2a_dispatch(
        source_agent="orchestrator",
        target_agent="search_agent",
        trace_id=None,
    )
    assert decision.needs_approval


def test_a2a_dispatch_to_unregistered_denied():
    guard = _guard()
    decision = guard.authorize_a2a_dispatch(
        source_agent="orchestrator",
        target_agent="rogue_agent",
        trace_id="trace-test",
    )
    assert not decision.allowed


# --- Semantic router: route_with_chain (Bài tập 3.1) ---

def _router() -> SemanticRouter:
    return SemanticRouter(
        agents=[
            AgentCapability("search_agent", "tìm kiếm web tài liệu", ["search", "web"]),
            AgentCapability("database_agent", "sql metrics database", ["sql", "metrics"]),
            AgentCapability("synthesis_agent", "tóm tắt báo cáo", ["summary", "report"]),
        ]
    )


def test_route_with_chain_picks_best_match():
    router = _router()
    result = router.route_with_chain(
        "tìm kiếm tài liệu web", ["search_agent", "database_agent", "orchestrator"]
    )
    assert result == "search_agent"


def test_route_with_chain_falls_back_when_no_match():
    router = _router()
    result = router.route_with_chain(
        "xyzzy khôngliênquan gì", ["search_agent", "database_agent", "orchestrator"]
    )
    assert result == "orchestrator"
