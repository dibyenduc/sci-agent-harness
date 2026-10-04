from harness.evalkit.tags import failure_tags

TASK = {"id": "event-01", "category": "event",
        "checks": [{"type": "status_is", "value": "done"},
                   {"type": "action_called", "tool": "draft_experiment"}]}
OUTS = [{"type": "status_is", "ok": False, "detail": ""},
        {"type": "action_called", "ok": False, "detail": ""}]
TEXT = '[{"name": "compare_to_spec", "parameters": {"formulation": "F-0083"}}]'


def test_calls_as_text_when_no_calls_and_tool_name_in_final():
    r = {"status": "ungrounded", "final": TEXT}
    tags = failure_tags(TASK, r, OUTS, [])
    assert tags == ["ungrounded", "no_tool_use", "calls_as_text", "missing_action"]


def test_no_calls_without_tool_name_is_plain_no_tool_use():
    r = {"status": "ungrounded", "final": "I looked at it and it seems fine."}
    tags = failure_tags(TASK, r, OUTS, [])
    assert "no_tool_use" in tags and "calls_as_text" not in tags


def test_tool_name_in_final_but_real_calls_made_is_not_flagged():
    r = {"status": "done", "final": "I used compare_to_spec and found it fails."}
    tags = failure_tags(TASK, r, OUTS, [{"kind": "tool_call"}])
    assert "calls_as_text" not in tags and "no_tool_use" not in tags


def test_crash_is_never_calls_as_text():
    r = {"status": "error:ConnectError", "final": TEXT}
    tags = failure_tags(TASK, r, OUTS, [])
    assert "calls_as_text" not in tags
