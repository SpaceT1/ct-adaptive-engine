"""Tests for the simulation study and the command-line interface."""

import csv
import json

import pytest

from ct_adaptive.cli import main
from ct_adaptive.simulation import (
    PROFILES,
    completion_curve,
    mean_trajectory,
    run_study,
    simulate_learner,
    summarise,
)


def test_same_seed_gives_identical_results():
    """Reproducibility: a fixed seed must reproduce every interaction exactly."""
    a = run_study(learners_per_profile=5, max_steps=80, seed=7)
    b = run_study(learners_per_profile=5, max_steps=80, seed=7)
    assert [r.history for r in a] == [r.history for r in b]


def test_different_seed_changes_results():
    a = run_study(learners_per_profile=5, max_steps=80, seed=1)
    b = run_study(learners_per_profile=5, max_steps=80, seed=2)
    assert [r.history for r in a] != [r.history for r in b]


def test_learner_stops_at_max_steps():
    result = simulate_learner("slow", 0, seed=3, max_steps=10)
    assert result.steps <= 10
    assert len(result.trajectory) == result.steps


def test_faster_profiles_need_fewer_tasks():
    """Sanity check of the study: fast < average < slow in median tasks."""
    rows = {r["profile"]: r for r in summarise(run_study(30, 200, seed=11))}
    assert (
        rows["fast"]["median_tasks_to_complete"]
        < rows["average"]["median_tasks_to_complete"]
        < rows["slow"]["median_tasks_to_complete"]
    )


def test_summary_rates_are_probabilities():
    for row in summarise(run_study(5, 100, seed=5)):
        for key in ("completion_rate", "false_mastery_rate", "missed_mastery_rate"):
            assert 0.0 <= row[key] <= 1.0


def test_curves_have_requested_length_and_are_monotone():
    results = run_study(5, 60, seed=9)
    for name in PROFILES:
        completion = completion_curve(results, name, 60)
        assert len(completion) == 60
        assert all(x <= y for x, y in zip(completion, completion[1:], strict=False))
        assert len(mean_trajectory(results, name, 60)) == 60


def test_curves_for_unknown_profile_are_empty():
    results = run_study(2, 20, seed=1)
    assert completion_curve(results, "nonexistent", 10) == []
    assert mean_trajectory(results, "nonexistent", 10) == []


def test_invalid_study_size_rejected():
    with pytest.raises(ValueError):
        run_study(learners_per_profile=0)


def test_cli_writes_all_outputs(tmp_path, capsys):
    out = tmp_path / "res"
    assert main(["--learners", "3", "--max-steps", "60", "--seed", "1", "--out", str(out)]) == 0
    for name in ("interactions.csv", "learners.csv", "summary.csv", "metadata.json"):
        assert (out / name).exists()
    assert (out / "completion.png").stat().st_size > 0
    meta = json.loads((out / "metadata.json").read_text())
    assert meta["seed"] == 1 and meta["engine_params"]["p_init"] == 0.10
    with (out / "summary.csv").open() as fh:
        assert len(list(csv.DictReader(fh))) == len(PROFILES)
    assert "results written" in capsys.readouterr().out


def test_cli_no_plot(tmp_path):
    out = tmp_path / "res"
    assert main(["--learners", "2", "--max-steps", "30", "--out", str(out), "--no-plot"]) == 0
    assert not (out / "completion.png").exists()


def test_cli_rejects_non_positive_sizes(tmp_path, capsys):
    assert main(["--learners", "0", "--out", str(tmp_path)]) == 2
    assert "error" in capsys.readouterr().err
