"""Decision layer: the nine adaptation rules of thesis Section 2.2.3.

Group 1 -- skill selection
    R1.1  practise the weakest active skill (active = P(L) below the mastery threshold)
    R1.2  at most ``max_streak`` consecutive tasks on one skill (interleaving)
    R1.3  every ``review_every`` tasks, one review task for a mastered skill

Group 2 -- difficulty selection (challenge-skill balance)
    R2.1  P(L) < 0.40          -> level 1
    R2.2  0.40 <= P(L) < 0.70  -> level 2
    R2.3  P(L) >= 0.70         -> level 3

Group 3 -- immediate support
    R3.1  two incorrect in a row  -> next task in that skill one level lower, with a hint
    R3.2  three correct in a row at the same level -> next task one level higher
    R3.3  an answer given after viewing a hint updates the model as incorrect

Every :class:`Decision` lists the rules that produced it, so each adaptation
step can be explained -- a design requirement of the thesis.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .bkt import BKTParams, update

MIN_LEVEL, MAX_LEVEL = 1, 3
ZONE_LOW, ZONE_HIGH = 0.40, 0.70


@dataclass
class SkillState:
    """Per-skill state kept by the engine."""

    p_mastery: float
    correct_streak: int = 0
    incorrect_streak: int = 0
    streak_level: int | None = None  # level at which the current streak was built
    level_override: int | None = None  # set by R3.1 / R3.2 for the next task in this skill
    hint_pending: bool = False  # set by R3.1
    last_reviewed: int = -1  # task index of the last review (R1.3)


@dataclass(frozen=True)
class Decision:
    """What the engine asks the game to present next."""

    skill: str
    difficulty: int
    hint: bool
    review: bool
    rules: tuple[str, ...]


def zone_level(p_mastery: float) -> tuple[int, str]:
    """Rules R2.1-R2.3: map a mastery estimate to a difficulty level."""
    if p_mastery < ZONE_LOW:
        return 1, "R2.1"
    if p_mastery < ZONE_HIGH:
        return 2, "R2.2"
    return 3, "R2.3"


@dataclass
class AdaptiveEngine:
    """BKT learner model plus the nine adaptation rules for one learner."""

    skills: list[str]
    params: BKTParams = field(default_factory=BKTParams)
    max_streak: int = 3
    review_every: int = 15
    state: dict[str, SkillState] = field(init=False)
    tasks_completed: int = field(init=False, default=0)
    history: list[dict] = field(init=False, default_factory=list)
    _last_skill: str | None = field(init=False, default=None)
    _same_skill_count: int = field(init=False, default=0)
    _last_review_at: int = field(init=False, default=-1)

    def __post_init__(self) -> None:
        if not self.skills:
            raise ValueError("at least one skill is required")
        if len(set(self.skills)) != len(self.skills):
            raise ValueError("skill names must be unique")
        self.state = {s: SkillState(p_mastery=self.params.p_init) for s in self.skills}

    # ------------------------------------------------------------------ queries
    def mastery(self) -> dict[str, float]:
        """Current mastery vector, one probability per skill."""
        return {s: st.p_mastery for s, st in self.state.items()}

    def active_skills(self) -> list[str]:
        """Skills below the mastery threshold, weakest first (ties: declaration order)."""
        thr = self.params.mastery_threshold
        active = [s for s in self.skills if self.state[s].p_mastery < thr]
        return sorted(active, key=lambda s: self.state[s].p_mastery)

    def is_complete(self) -> bool:
        """True when every skill has reached the mastery threshold."""
        return not self.active_skills()

    # ----------------------------------------------------------------- decide
    def next_task(self) -> Decision | None:
        """Choose skill, difficulty and support for the next task.

        Returns ``None`` when all skills are mastered.
        """
        review = self._review_candidate()
        if review is not None:
            st = self.state[review]
            level, zone_rule = zone_level(st.p_mastery)
            return Decision(review, level, False, True, ("R1.3", zone_rule))

        active = self.active_skills()
        if not active:
            return None

        skill, rules = active[0], ["R1.1"]
        if (
            skill == self._last_skill
            and self._same_skill_count >= self.max_streak
            and len(active) > 1
        ):
            skill = active[1]
            rules.append("R1.2")

        st = self.state[skill]
        if st.level_override is not None:
            level = st.level_override
            rules.append("R3.1" if st.hint_pending else "R3.2")
        else:
            level, zone_rule = zone_level(st.p_mastery)
            rules.append(zone_rule)
        return Decision(skill, level, st.hint_pending, False, tuple(rules))

    def _review_candidate(self) -> str | None:
        """R1.3: a mastered skill due for review, least recently reviewed first."""
        due = (
            self.tasks_completed > 0
            and self.tasks_completed % self.review_every == 0
            and self._last_review_at != self.tasks_completed
        )
        if not due:
            return None
        thr = self.params.mastery_threshold
        mastered = [s for s in self.skills if self.state[s].p_mastery >= thr]
        if not mastered:
            return None
        return min(mastered, key=lambda s: self.state[s].last_reviewed)

    # ----------------------------------------------------------------- record
    def record(self, decision: Decision, correct: bool, used_hint: bool = False) -> float:
        """Update the learner model with one response and return the new P(L).

        ``used_hint`` marks an answer given after viewing a hint (rule R3.3).
        """
        st = self.state[decision.skill]
        p_before = st.p_mastery
        rules = list(decision.rules)

        # R3.3: assisted success does not demonstrate independent mastery.
        observed = correct and not used_hint
        if used_hint:
            rules.append("R3.3")
        st.p_mastery = update(st.p_mastery, observed, self.params)

        # The override and the hint apply to one task only.
        st.level_override = None
        st.hint_pending = False

        if decision.review:
            st.last_reviewed = self.tasks_completed
            self._last_review_at = self.tasks_completed
        else:
            self._update_streaks(st, decision.difficulty, correct, used_hint)

        if decision.skill == self._last_skill:
            self._same_skill_count += 1
        else:
            self._last_skill, self._same_skill_count = decision.skill, 1

        self.history.append(
            {
                "step": len(self.history) + 1,
                "skill": decision.skill,
                "difficulty": decision.difficulty,
                "review": decision.review,
                "hint_offered": decision.hint,
                "used_hint": used_hint,
                "correct": correct,
                "p_before": round(p_before, 6),
                "p_after": round(st.p_mastery, 6),
                "rules": "+".join(rules),
            }
        )
        self.tasks_completed += 1
        return st.p_mastery

    def _update_streaks(self, st: SkillState, level: int, correct: bool, used_hint: bool) -> None:
        """Maintain the counters behind rules R3.1 and R3.2."""
        # R3.2 counts correct answers "at the current difficulty", so a level
        # change restarts that count. R3.1 counts errors "within a skill",
        # regardless of level, so the error count survives a level change.
        if st.streak_level != level:
            st.correct_streak = 0
            st.streak_level = level

        if used_hint:  # assisted answer: neither a clean success nor a failure
            st.correct_streak = st.incorrect_streak = 0
        elif correct:
            st.correct_streak += 1
            st.incorrect_streak = 0
        else:
            st.incorrect_streak += 1
            st.correct_streak = 0

        if st.incorrect_streak >= 2:  # R3.1
            st.level_override = max(MIN_LEVEL, level - 1)
            st.hint_pending = True
            st.incorrect_streak = 0
        elif st.correct_streak >= 3:  # R3.2
            st.level_override = min(MAX_LEVEL, level + 1)
            st.correct_streak = 0
