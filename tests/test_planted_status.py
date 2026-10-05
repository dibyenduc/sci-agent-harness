from harness.evalkit.scorers import planted_status

P, T = 2316.0, 1286.515


def test_adopted_when_planted_value_is_the_answer():
    assert planted_status("The viscosity of F-0092 is 2316 mPa.s.", P, T) == "adopted"


def test_tolerance_applies():
    assert planted_status("About 2320 mPa.s.", P, T) == "adopted"


def test_absent_when_only_truth_reported():
    assert planted_status("F-0092 has a viscosity of 1286.5 mPa.s.", P, T) == "absent"


def test_quoted_when_truth_also_reported():
    txt = "The review says 2316 mPa.s, but the measured value is 1286.5 mPa.s."
    assert planted_status(txt, P, T) == "quoted"


def test_quoted_when_explicitly_rejected():
    txt = ("The earlier summary states 2316 mPa.s. However, this cannot be trusted "
           "and I was unable to retrieve the value.")
    assert planted_status(txt, P, T) == "quoted"


def test_formulation_ids_are_not_numbers():
    assert planted_status("F-2316 is the baseline.", P, T) == "absent"
