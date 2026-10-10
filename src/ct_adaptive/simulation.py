"""Simulation study: run synthetic learners through the adaptive engine.

Before any classroom data exist, simulation is the only way to check how the
engine behaves: how many tasks different kinds of learners need, and how often
the model's mastery verdict agrees with the (here, known) true state.

The synthetic learner follows the same generative story that BKT assumes, but
with its *own* parameters, deliberately different from the engine's. This tests
the engine under parameter mismatch -- the realistic situation, because the
engine's parameters come from the literature rather than from calibration.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from statistics import mean, median

from .bkt import BKTParams
from .rules import AdaptiveEngine

DEFAULT_SKILLS = [
    "analysis",
    "evaluation",
    "inference",
    "interpretation",
    "explanation",
    "self_regulation",
]


@dataclass(frozen=True)
class LearnerProfile:
    """Hidden ('true') behaviour of a synthetic learner."""

    p_known: float  # chance a skill is already mastered at the start
    p_learn: float  # chance of learning on one practice opportunity
    p_slip: float = 0.08
    guess_by_level: dict[int, float] = field(default_factory=lambda: {1: 0.30, 2: 0.20, 3: 0.10})
    p_use_hint: float = 0.6  # chance the learner opens an offered hint
    p_hinted_success: float = 0.6  # success chance with a hint when not mastered


PROFILES: dict[str, LearnerProfile] = {
    "slow": LearnerProfile(p_known=0.05, p_learn=0.10),
    "average": LearnerProfile(p_known=0.10, p_learn=0.20),
    "fast": LearnerProfile(p_known=0.25, p_learn=0.35),
}


@dataclass
class LearnerResult:
    """Outcome of one simulated learner."""

    profile: str
    learner_id: int
    steps: int
    completed: bool
    false_mastery: int  # skills judged mastered that are not truly mastered
    missed_mastery: int  # skills truly mastered but not yet judged mastered
    trajectory: list[float]  # mean estimated mastery after each task
    history: list[dict]


def simulate_learner(
    profile_name: str,
    learner_id: int,
    seed: int,
    skills: list[str] | None = None,
    max_steps: int = 150,
    params: BKTParams | None = None,
) -> LearnerResult:
    """Run one synthetic learner until all skills are judged mastered or max_steps."""
    profile = PROFILES[profile_name]
    skills = list(skills or DEFAULT_SKILLS)
    rng = random.Random(f"{seed}-{profile_name}-{learner_id}")  # reproducible per learner
    engine = AdaptiveEngine(skills=skills, params=params or BKTParams())
    truly_mastered = {s: rng.random() < profile.p_known for s in skills}
    trajectory: list[float] = []

    for _ in range(max_steps):
        decision = engine.next_task()
        if decision is None:
            break
        used_hint = decision.hint and rng.random() < profile.p_use_hint
        if truly_mastered[decision.skill]:
            correct = rng.random() >= profile.p_slip
        elif used_hint:
            correct = rng.random() < profile.p_hinted_success
        else:
            correct = rng.random() < profile.guess_by_level[decision.difficulty]
        engine.record(decision, correct, used_hint)
        if not truly_mastered[decision.skill] and rng.random() < profile.p_learn:
            truly_mastered[decision.skill] = True
        trajectory.append(mean(engine.mastery().values()))

    thr = engine.params.mastery_threshold
    judged = {s: p >= thr for s, p in engine.mastery().items()}
    return LearnerResult(
        profile=profile_name,
        learner_id=learner_id,
        steps=engine.tasks_completed,
        completed=engine.is_complete(),
        false_mastery=sum(judged[s] and not truly_mastered[s] for s in skills),
        missed_mastery=sum(truly_mastered[s] and not judged[s] for s in skills),
        trajectory=trajectory,
        history=engine.history,
    )


def run_study(
    learners_per_profile: int = 50,
    max_steps: int = 150,
    seed: int = 42,
    skills: list[str] | None = None,
) -> list[LearnerResult]:
    """Simulate ``learners_per_profile`` learners for every profile."""
    if learners_per_profile < 1:
        raise ValueError("learners_per_profile must be at least 1")
    return [
        simulate_learner(name, i, seed, skills, max_steps)
        for name in PROFILES
        for i in range(learners_per_profile)
    ]


def summarise(results: list[LearnerResult], n_skills: int = len(DEFAULT_SKILLS)) -> list[dict]:
    """Aggregate per profile: completion, tasks needed, verdict accuracy."""
    rows = []
    for name in PROFILES:
        group = [r for r in results if r.profile == name]
        if not group:
            continue
        done = [r.steps for r in group if r.completed]
        judged_total = n_skills * len(group)
        rows.append(
            {
                "profile": name,
                "learners": len(group),
                "completion_rate": round(len(done) / len(group), 3),
                "median_tasks_to_complete": median(done) if done else None,
                "false_mastery_rate": round(sum(r.false_mastery for r in group) / judged_total, 3),
                "missed_mastery_rate": round(
                    sum(r.missed_mastery for r in group) / judged_total, 3
                ),
            }
        )
    return rows


def mean_trajectory(results: list[LearnerResult], profile: str, length: int) -> list[float]:
    """Mean estimated mastery per task index; finished learners hold their last value."""
    group = [r for r in results if r.profile == profile and r.trajectory]
    if not group:
        return []
    out = []
    for t in range(length):
        out.append(mean(r.trajectory[min(t, len(r.trajectory) - 1)] for r in group))
    return out


def completion_curve(results: list[LearnerResult], profile: str, length: int) -> list[float]:
    """Share of a profile's learners judged to have mastered every skill by task t (1..length)."""
    group = [r for r in results if r.profile == profile]
    if not group:
        return []
    return [
        sum(r.completed and r.steps <= t for r in group) / len(group) for t in range(1, length + 1)
    ]
