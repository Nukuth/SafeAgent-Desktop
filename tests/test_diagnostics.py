from safeagent.shared.diagnostics import build_run_diagnostics


def test_run_diagnostics_summarizes_completed_run():
    events = [
        {
            "event_id": "evt_1",
            "agent": "graph_runner",
            "event_type": "graph_run_completed",
            "summary": "graph ok",
            "risk_level": "medium",
            "network_mode": "api_only",
            "details": {
                "edge_decisions": [
                    {"from": "rule_reviewer", "to": "human_approval", "selected": True},
                    {"from": "human_approval", "to": "executor", "selected": False, "reason": "approval_valid=False"},
                ]
            },
        },
        {
            "event_id": "evt_2",
            "agent": "summarizer",
            "event_type": "run_completed",
            "summary": "done",
            "risk_level": "medium",
            "network_mode": "api_only",
            "details": {},
        },
    ]
    diagnostics = build_run_diagnostics(events, [{"approval_id": "approval_1"}])
    assert diagnostics["status"] == "completed"
    assert diagnostics["event_count"] == 2
    assert diagnostics["approval_count"] == 1
    assert diagnostics["risk_level"] == "medium"
    assert diagnostics["edge_decisions"] == {"selected": 1, "skipped": 1, "failed": 0}
    assert diagnostics["agents"] == ["graph_runner", "summarizer"]


def test_run_diagnostics_extracts_blocking_reason_and_redacts():
    events = [
        {
            "event_id": "evt_1",
            "agent": "executor",
            "event_type": "execution_skipped",
            "summary": "blocked",
            "risk_level": "high",
            "network_mode": "api_only",
            "details": {
                "reason": "blocked token sk-abcdefghijklmnopqrstuvwxyz",
                "plan_hash": "plan_1",
                "command_hash": "cmd_1",
            },
        }
    ]
    diagnostics = build_run_diagnostics(events, [])
    serialized = str(diagnostics)
    assert diagnostics["status"] == "blocked_or_skipped"
    assert diagnostics["blocking_reasons"][0]["reason"] == "blocked token [REDACTED]"
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in serialized


def test_run_diagnostics_extracts_graph_node_error():
    events = [
        {
            "event_id": "evt_1",
            "agent": "graph_runner",
            "event_type": "graph_node_failed",
            "summary": "graph failed",
            "risk_level": "low",
            "network_mode": "api_only",
            "details": {
                "node_results": [
                    {"node_id": "planner", "status": "completed", "error": None},
                    {
                        "node_id": "search_agent",
                        "status": "failed",
                        "error": {
                            "code": "validation.failed",
                            "module": "local_worker.graph_runner",
                            "message": "bad condition",
                        },
                    },
                ],
                "edge_decisions": [
                    {
                        "from": "planner",
                        "to": "search_agent",
                        "selected": False,
                        "reason": "Unknown graph edge condition",
                    }
                ],
            },
        },
        {
            "event_id": "evt_2",
            "agent": "graph_runner",
            "event_type": "run_failed",
            "summary": "run failed",
            "risk_level": "low",
            "network_mode": "api_only",
            "details": {},
        },
    ]
    diagnostics = build_run_diagnostics(events, [])
    assert diagnostics["status"] == "failed"
    assert diagnostics["error_count"] == 2
    assert diagnostics["errors"][0]["error"]["code"] == "validation.failed"
    assert diagnostics["edge_decisions"] == {"selected": 0, "skipped": 1, "failed": 1}
