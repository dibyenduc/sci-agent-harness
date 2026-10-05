from harness.evalkit.scorers import verdict


def test_qwen_style_none_after_failing_properties_is_pass():
    t = ("F-0031 meets the full coating_std spec with all properties passing.\n"
         "**Answer:** pass\n**Failing properties:** None. All checks are within spec limits.")
    assert verdict(t) == "pass"


def test_plain_none_after_colon_is_pass():
    assert verdict("Result: pass. Failing properties: none.") == "pass"


def test_no_failing_properties_before_is_still_pass():
    assert verdict("No failing properties; the formulation meets spec.") == "pass"


def test_real_failure_sentences_stay_fail():
    assert verdict("F-0031 fails the coating_std spec for viscosity.") == "fail"
    assert verdict("The failing property: hardness.") == "fail"
    assert verdict("The failing properties are: hardness and gloss.") == "fail"


def test_none_listed_then_a_real_failure_stays_fail():
    assert verdict("Failing properties: none, but viscosity fails the limit.") == "fail"


def test_unknown_stays_unknown():
    assert verdict("It seems that the tool call returned an error.") == "unknown"
