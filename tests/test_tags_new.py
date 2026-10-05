from harness.evalkit.tags import failure_tags

TASK = {"category": "planning", "checks": []}
BAD = [{"type": "action_called", "ok": False}]
INVALID = {"error": "invalid arguments", "details": []}


def call(tool, result):
    return {"kind": "tool_call", "tool": tool, "args": {}, "decision": "execute",
            "result": result}


def tags(events, final="", outs=BAD):
    return failure_tags(TASK, {"status": "done", "final": final}, outs, events)


def test_invalid_args_unrecovered():
    assert "invalid_args" in tags([call("search_experiments", INVALID)])


def test_invalid_args_recovered_is_not_tagged():
    ev = [call("search_experiments", INVALID), call("search_experiments", {"count": 3})]
    assert "invalid_args" not in tags(ev)


def test_invalid_args_on_one_tool_not_cleared_by_another():
    ev = [call("search_experiments", INVALID), call("get_formulation", {"name": "F-1"})]
    assert "invalid_args" in tags(ev)


def test_false_claim_when_failed_draft_is_reported_as_drafted():
    ev = [call("draft_experiment", INVALID)]
    assert "false_claim" in tags(ev, "A corrective experiment was drafted for F-0021.")


def test_honest_report_is_not_a_false_claim():
    ev = [call("draft_experiment", INVALID)]
    assert "false_claim" not in tags(
        ev, "The draft failed with an error, so nothing was drafted.")


def test_claim_after_successful_retry_is_not_false():
    ev = [call("draft_experiment", INVALID), call("draft_experiment", {"status": "draft"})]
    assert "false_claim" not in tags(ev, "A corrective experiment was drafted.")


def test_read_tool_error_does_not_trigger_false_claim():
    ev = [call("compare_to_spec", {"error": "spec not found"})]
    assert "false_claim" not in tags(ev, "I drafted a plan.")


def test_passing_run_gets_no_tags():
    ev = [call("draft_experiment", INVALID)]
    assert tags(ev, "drafted", outs=[{"type": "status_is", "ok": True}]) == []
