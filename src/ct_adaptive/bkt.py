"""Bayesian Knowledge Tracing (Corbett & Anderson, 1995).

Each skill is modelled as a binary latent variable (mastered / not mastered)
that is observed indirectly through correct and incorrect responses. The model
needs only four parameters and closed-form arithmetic, so one update costs a
few floating-point operations -- no training, no GPU.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BKTParams:
    """The four BKT parameters plus the mastery threshold.

    Defaults are the literature-based values adopted in Table 2.1 of the thesis.
    """

    p_init: float = 0.10  # P(L0): prior probability the skill is already mastered
    p_transit: float = 0.25  # P(T): probability of learning on one practice opportunity
    p_slip: float = 0.10  # P(S): incorrect answer despite mastery
    p_guess: float = 0.20  # P(G): correct answer without mastery
    mastery_threshold: float = 0.95

    def __post_init__(self) -> None:
        for name in ("p_init", "p_transit", "p_slip", "p_guess", "mastery_threshold"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0, 1], got {value}")
        # Without this condition a correct answer could *lower* the mastery
        # estimate, which makes the model degenerate (Baker et al., 2008).
        if self.p_slip + self.p_guess >= 1.0:
            raise ValueError("p_slip + p_guess must be < 1 for an identifiable model")


def posterior(p_mastery: float, correct: bool, params: BKTParams) -> float:
    """Condition the mastery estimate on one observed response (Bayes' rule)."""
    if correct:
        num = p_mastery * (1.0 - params.p_slip)
        den = num + (1.0 - p_mastery) * params.p_guess
    else:
        num = p_mastery * params.p_slip
        den = num + (1.0 - p_mastery) * (1.0 - params.p_guess)
    return num / den


def update(p_mastery: float, correct: bool, params: BKTParams) -> float:
    """Full BKT step: Bayesian conditioning followed by the learning transition."""
    cond = posterior(p_mastery, correct, params)
    return cond + (1.0 - cond) * params.p_transit


def p_correct(p_mastery: float, params: BKTParams) -> float:
    """Predicted probability that the next response will be correct."""
    return p_mastery * (1.0 - params.p_slip) + (1.0 - p_mastery) * params.p_guess
