"""One or more tests per adaptation rule (thesis Section 2.2.3)."""

import pytest

from ct_adaptive.bkt import BKTParams
from ct_adaptive.rules import AdaptiveEngine, Decision, zone_level

SKILLS = ["analysis", "evaluation", "inference"]


def make(**kwargs) -> AdaptiveEngine:
    return AdaptiveEngine(skills=list(SKILLS), **kwargs)


def answer(engine: AdaptiveEngine, correct: bool, used_hint: bool = False) -> Decision:
    decision = engine.next_task()
    assert decision is not None
    engine.record(decision, correct, used_hint)
    return decision


# --- construction -------------------------------------------------------------
def test_empty_skill_list_rejected():
    with pytest.raises(ValueError):
        AdaptiveEngine(skills=[])


def test_duplicate_skills_rejected():
    with pytest.raises(ValueError):
        AdaptiveEngine(skills=["analysis", "analysis"])


def test_all_skills_start_at_prior():
    engine = make()
    assert set(engine.mastery().values()) == {0.10}


# --- R1.1 -------------------------------------------------------------------
def test_r1_1_weakest_skill_first():
    engine = make()
    engine.state["evaluation"].p_mastery = 0.05
    decision = engine.next_task()
    assert decision.skill == "evaluation"
    assert "R1.1" in decision.rules


def test_r1_1_mastered_skill_not_selected():
    engine = make()
    engine.state["analysis"].p_mastery = 0.99
    engine.state["evaluation"].p_mastery = 0.99
    assert engine.next_task().skill == "inference"


# --- R1.2 -------------------------------------------------------------------
def test_r1_2_interleaving_after_three_tasks_on_one_skill():
    engine = make()
    engine.state["analysis"].p_mastery = 0.01  # stays the weakest skill
    skills = []
    for _ in range(4):
        d = engine.next_task()
        skills.append(d.skill)
        engine.record(d, correct=False)
        engine.state["analysis"].p_mastery = min(engine.state["analysis"].p_mastery, 0.01)
    assert skills[:3] == ["analysis"] * 3
    assert skills[3] != "analysis"


def test_r1_2_not_applied_when_only_one_skill_active():
    engine = make()
    engine.state["evaluation"].p_mastery = 0.99
    engine.state["inference"].p_mastery = 0.99
    for _ in range(5):
        assert answer(engine, correct=False).skill == "analysis"


# --- R1.3 -------------------------------------------------------------------
def test_r1_3_review_of_mastered_skill_every_fifteen_tasks():
    engine = make()
    engine.state["evaluation"].p_mastery = 0.99
    reviews = []
    for _ in range(31):
        d = engine.next_task()
        engine.record(d, correct=d.review)  # pass reviews, fail ordinary tasks
        if d.review:
            reviews.append(engine.tasks_completed - 1)
    assert reviews == [15, 30]


def test_r1_3_incorrect_review_returns_skill_to_rotation():
    engine = make(review_every=1)
    for skill in SKILLS:
        engine.state[skill].p_mastery = 0.99
    engine.state["analysis"].p_mastery = 0.10
    answer(engine, correct=True)  # ordinary task, tasks_completed -> 1
    d = engine.next_task()
    assert d.review and "R1.3" in d.rules
    engine.record(d, correct=False)
    assert d.skill in engine.active_skills()


def test_no_review_when_nothing_mastered():
    engine = make(review_every=1)
    answer(engine, correct=False)
    assert not engine.next_task().review


# --- R2.x -------------------------------------------------------------------
@pytest.mark.parametrize(
    "p, level, rule",
    [
        (0.10, 1, "R2.1"),
        (0.399, 1, "R2.1"),
        (0.40, 2, "R2.2"),
        (0.699, 2, "R2.2"),
        (0.70, 3, "R2.3"),
        (0.94, 3, "R2.3"),
    ],
)
def test_r2_zone_boundaries(p, level, rule):
    assert zone_level(p) == (level, rule)


def test_r2_applied_by_engine():
    engine = make()
    for skill in SKILLS:
        engine.state[skill].p_mastery = 0.55
    d = engine.next_task()
    assert d.difficulty == 2 and "R2.2" in d.rules


# --- R3.1 -------------------------------------------------------------------
def test_r3_1_two_errors_lower_level_and_offer_hint():
    params = BKTParams(p_transit=0.0, p_guess=0.45, p_slip=0.45)  # estimate moves slowly
    engine = AdaptiveEngine(skills=["analysis"], params=params)
    engine.state["analysis"].p_mastery = 0.80  # zone -> level 3
    first = answer(engine, correct=False)
    second = answer(engine, correct=False)
    assert first.difficulty == second.difficulty == 3
    d = engine.next_task()
    assert d.hint is True
    assert d.difficulty == second.difficulty - 1
    assert "R3.1" in d.rules


def test_r3_1_never_below_level_one():
    engine = AdaptiveEngine(skills=["analysis"])
    answer(engine, correct=False)
    answer(engine, correct=False)
    d = engine.next_task()
    assert d.difficulty == 1 and d.hint


def test_r3_1_hint_applies_to_one_task_only():
    engine = AdaptiveEngine(skills=["analysis"])
    answer(engine, correct=False)
    answer(engine, correct=False)
    answer(engine, correct=True)  # the hinted task
    assert engine.next_task().hint is False


# --- R3.2 -------------------------------------------------------------------
def test_r3_2_three_correct_raise_level_above_zone():
    params = BKTParams(p_transit=0.0, p_guess=0.45, p_slip=0.45)  # estimate moves slowly
    engine = AdaptiveEngine(skills=["analysis"], params=params)
    for _ in range(3):
        assert answer(engine, correct=True).difficulty == 1
    d = engine.next_task()
    assert d.difficulty == 2 and "R3.2" in d.rules
    assert zone_level(engine.state["analysis"].p_mastery)[0] == 1  # zone alone says 1


def test_r3_2_never_above_level_three():
    engine = AdaptiveEngine(skills=["analysis"])
    engine.state["analysis"].p_mastery = 0.75
    for _ in range(3):
        answer(engine, correct=True)
        engine.state["analysis"].p_mastery = 0.75  # keep below mastery
    assert engine.next_task().difficulty == 3


# --- R3.3 -------------------------------------------------------------------
def test_r3_3_hinted_success_counts_as_incorrect_for_model():
    plain, hinted = AdaptiveEngine(skills=["analysis"]), AdaptiveEngine(skills=["analysis"])
    p_plain = plain.record(plain.next_task(), correct=True)
    p_hinted = hinted.record(hinted.next_task(), correct=True, used_hint=True)
    p_wrong = AdaptiveEngine(skills=["analysis"])
    p_incorrect = p_wrong.record(p_wrong.next_task(), correct=False)
    assert p_hinted == pytest.approx(p_incorrect)
    assert p_hinted < p_plain
    assert "R3.3" in hinted.history[-1]["rules"]
    assert hinted.history[-1]["correct"] is True  # feedback still shows success


# --- completion and logging ---------------------------------------------------
def test_engine_completes_when_all_skills_mastered():
    engine = make()
    for _ in range(200):
        d = engine.next_task()
        if d is None:
            break
        engine.record(d, correct=True)
    assert engine.is_complete()
    assert engine.next_task() is None


def test_history_records_every_step():
    engine = make()
    for _ in range(5):
        answer(engine, correct=True)
    assert [h["step"] for h in engine.history] == [1, 2, 3, 4, 5]
    assert all(h["rules"] for h in engine.history)
