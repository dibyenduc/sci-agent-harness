import pandas as pd
from harness.evalkit.report import build_report


def test_report_summarizes_pass_rate_and_tags(tmp_path):
    pd.DataFrame({
        "task_id": ["a", "b"], "passed": ["True", "False"], "clean": ["True", "True"],
        "latency_s": ["1", "3"], "tokens": ["100", "300"], "model": ["m", "m"],
        "engine": ["plain", "plain"], "temperature": ["0.7", "0.7"],
        "tags": ["", "invalid_args"],
    }).to_csv(tmp_path / "m-plain-t0.7-phase5c.csv", index=False)
    md = build_report(tmp_path)
    assert "| phase5c | m | plain | 0.7 | 2 | 0.50 | 1.00 | 2.0 | 200 | invalid_args x1 |" in md


def test_pre_tagging_csv_is_marked(tmp_path):
    pd.DataFrame({
        "task_id": ["a"], "passed": ["True"], "clean": ["True"], "latency_s": ["2"],
        "tokens": ["50"], "model": ["m"], "engine": ["plain"], "temperature": ["0.0"],
    }).to_csv(tmp_path / "m-plain-t0.0.csv", index=False)
    md = build_report(tmp_path)
    assert "| core | m | plain | 0.0 | 1 | 1.00 |" in md and "n/a (pre-tagging)" in md
