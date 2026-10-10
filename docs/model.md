# The model

This document is the specification the code is tested against. Section
numbers refer to Chapter 2 of the thesis.

## 1. Estimation layer: Bayesian Knowledge Tracing (Section 2.2.1)

For each skill the engine keeps P(L), the probability that the skill is
mastered. After every response it applies two steps.

**Step 1 – condition on the evidence (Bayes' rule).**

Correct answer:

    P(L | correct) = P(L)(1 − P(S)) / [ P(L)(1 − P(S)) + (1 − P(L)) P(G) ]

Incorrect answer:

    P(L | incorrect) = P(L) P(S) / [ P(L) P(S) + (1 − P(L))(1 − P(G)) ]

**Step 2 – account for learning on this task.**

    P(L)new = P(L | answer) + (1 − P(L | answer)) · P(T)

Predicted chance of a correct answer: `P(L)(1 − P(S)) + (1 − P(L)) P(G)`.

### Worked example (default parameters)

| Step | Answer | P(L) after |
|---|---|---|
| start | – | 0.100 |
| 1 | correct | 0.500 |
| 2 | correct | 0.864 |
| 3 | incorrect | 0.581 |

These values are checked in `tests/test_bkt.py::test_worked_example_sequence`.

## 2. Decision layer: nine rules (Section 2.2.3)

| Rule | Condition | Action |
|---|---|---|
| R1.1 | always | choose the active skill (P(L) < 0.95) with the lowest P(L) |
| R1.2 | the same skill was chosen 3 times in a row | choose the next-weakest active skill |
| R1.3 | 15, 30, 45 … tasks completed and some skill is mastered | give one review task for the mastered skill reviewed longest ago; a wrong answer returns it to rotation |
| R2.1 | P(L) < 0.40 | difficulty 1 |
| R2.2 | 0.40 ≤ P(L) < 0.70 | difficulty 2 |
| R2.3 | P(L) ≥ 0.70 | difficulty 3 |
| R3.1 | 2 incorrect answers in a row within the skill | next task in that skill one level lower (min 1), with a hint |
| R3.2 | 3 correct answers in a row at the same level | next task in that skill one level higher (max 3) |
| R3.3 | the learner opened the hint | the answer updates P(L) as incorrect; the log keeps the real outcome |

R3.1 and R3.2 override R2.x for one task only.

## 3. Simulation (synthetic learners)

Each synthetic learner has a hidden true state per skill and its own
parameters (table below), deliberately different from the engine's, to test the
engine under parameter mismatch.

| Profile | Initially mastered | Learning per task | Slip | Guess at level 1 / 2 / 3 |
|---|---|---|---|---|
| slow | 5 % | 10 % | 8 % | 30 / 20 / 10 % |
| average | 10 % | 20 % | 8 % | 30 / 20 / 10 % |
| fast | 25 % | 35 % | 8 % | 30 / 20 / 10 % |

Hints: a learner opens an offered hint with probability 0.6 and then answers
correctly with probability 0.6 if the skill is not mastered.
