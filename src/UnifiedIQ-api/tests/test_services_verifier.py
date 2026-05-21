from app.services.verifier import _compare, extract_scalar


def test_extract_scalar_picks_first_numeric():
    assert extract_scalar([{"k": "a", "v": 42}]) == 42.0
    assert extract_scalar([{"k": "a", "v": 1.5}]) == 1.5
    assert extract_scalar([{"k": "a"}]) is None
    assert extract_scalar([]) is None
    # bools must not count as numeric (would otherwise return 1.0 for True)
    assert extract_scalar([{"x": True, "n": 7}]) == 7.0


def test_compare_tolerances():
    verdict, conf, diff = _compare(100.0, 100.5)
    assert verdict == "agree"
    assert conf >= 0.95
    assert diff < 0.01

    verdict, conf, diff = _compare(100.0, 102.0)
    assert verdict == "agree"
    assert 0.7 < conf < 0.95

    verdict, _, _ = _compare(100.0, 110.0)
    assert verdict == "inconclusive"

    verdict, conf, _ = _compare(100.0, 200.0)
    assert verdict == "disagree"
    assert conf < 0.3


def test_compare_zero_zero():
    verdict, conf, diff = _compare(0.0, 0.0)
    assert verdict == "agree"
    assert diff == 0.0
    assert conf > 0.9
