"""Tests for the BKT estimation layer.

Expected values are computed by hand from the formulas in Section 2.2.1 of the
thesis, so the tests check the implementation against the written model.
"""

import pytest

from ct_adaptive.bkt import BKTParams, p_correct, posterior, update

P = BKTParams()


def test_default_parameters_match_thesis_table_2_1():
    assert (P.p_init, P.p_transit, P.p_slip, P.p_guess) == (0.10, 0.25, 0.10, 0.20)
    assert P.mastery_threshold == 0.95


def test_posterior_after_correct_answer():
    # (0.10 * 0.90) / (0.10 * 0.90 + 0.90 * 0.20) = 0.09 / 0.27
    assert posterior(0.10, True, P) == pytest.approx(1 / 3)


def test_posterior_after_incorrect_answer():
    # (0.5 * 0.10) / (0.5 * 0.10 + 0.5 * 0.80) = 0.05 / 0.45
    assert posterior(0.5, False, P) == pytest.approx(1 / 9)


def test_worked_example_sequence():
    """Worked example of Section 2.2.4: correct, correct, incorrect."""
    p = P.p_init
    p = update(p, True, P)
    assert p == pytest.approx(0.500, abs=1e-3)
    p = update(p, True, P)
    assert p == pytest.approx(0.864, abs=1e-3)
    p = update(p, False, P)
    assert p == pytest.approx(0.581, abs=1e-3)


def test_correct_answer_never_lowers_estimate():
    for i in range(1, 100):
        p = i / 100
        assert update(p, True, P) >= p


def test_estimate_stays_a_probability():
    p = P.p_init
    for correct in [True] * 50 + [False] * 50:
        p = update(p, correct, P)
        assert 0.0 <= p <= 1.0


def test_p_correct_bounds():
    assert p_correct(0.0, P) == pytest.approx(P.p_guess)
    assert p_correct(1.0, P) == pytest.approx(1 - P.p_slip)


@pytest.mark.parametrize("field", ["p_init", "p_transit", "p_slip", "p_guess", "mastery_threshold"])
def test_out_of_range_parameter_rejected(field):
    with pytest.raises(ValueError):
        BKTParams(**{field: 1.5})


def test_degenerate_slip_guess_rejected():
    with pytest.raises(ValueError):
        BKTParams(p_slip=0.6, p_guess=0.5)
