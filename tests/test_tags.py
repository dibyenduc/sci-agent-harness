from harness.evalkit.tags import failure_tags

TRAP = {"id": "unit_trap-01", "category": "unit_trap",
        "checks": [{"type": "status_is", "value": "done"},
                   {"type": "final_number", "value": 4200.0, "rel_tol": 0.01}]}
LOOKUP = {"id": "lookup-01", "category": "lookup",
          "checks": [{"type": "status_is", "value": "done"},
                     {"type": "final_number", "value": 534.355, "rel_tol": 0.01}]}
CALL = [{"kind": "tool_call"}]


def outs(*failed):
    types = ["status_is", "final_number", "final_verdict", "final_only_formulation",
             "sql_equals", "action_called", "no_failed_actions"]
    return [{"type": t, "ok": t not in failed, "detail": ""} for t in types]


def test_pass_has_no_tags():
    assert failure_tags(LOOKUP, {"status": "done", "final": "534.355"}, outs(), CALL) == []


def test_unit_confusion_detected():
    r = {"status": "done", "final": "Viscosity is 4.2 mPa.s"}
    assert failure_tags(TRAP, r, outs("final_number"), CALL) == ["unit_confusion"]


def test_wrong_value_on_unit_trap_without_factor():
    r = {"status": "done", "final": "It is 999"}
    assert failure_tags(TRAP, r, outs("final_number"), CALL) == ["wrong_value"]


def test_wrong_value_on_lookup():
    r = {"status": "done", "final": "It is 4.2"}
    assert failure_tags(LOOKUP, r, outs("final_number"), CALL) == ["wrong_value"]


def test_no_tool_use_and_ungrounded():
    r = {"status": "ungrounded", "final": "x"}
    tags = failure_tags(LOOKUP, r, outs("status_is", "final_number"), [])
    assert tags == ["ungrounded", "no_tool_use", "wrong_value"]


def test_crash_does_not_add_no_tool_use():
    r = {"status": "error:ConnectError", "final": "boom"}
    tags = failure_tags(LOOKUP, r, outs("status_is", "final_number"), [])
    assert tags[0] == "crash" and "no_tool_use" not in tags


def test_state_and_action_tags():
    r = {"status": "done", "final": "ok"}
    tags = failure_tags(LOOKUP, r, outs("sql_equals", "action_called"), CALL)
    assert tags == ["unsafe_write", "missing_action"]


def test_loop_and_budget():
    assert failure_tags(LOOKUP, {"status": "loop_detected", "final": ""},
                        outs("status_is"), CALL) == ["loop"]
    assert failure_tags(LOOKUP, {"status": "max_steps", "final": ""},
                        outs("status_is"), CALL) == ["budget"]
