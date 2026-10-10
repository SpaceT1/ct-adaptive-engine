"""Command-line entry point: ``ct-simulate`` or ``python -m ct_adaptive``.

Runs the simulation study and writes, into ``--out``:

* ``interactions.csv`` -- every simulated task with the rules that fired;
* ``learners.csv``     -- one row per synthetic learner;
* ``summary.csv``      -- one row per learner profile;
* ``metadata.json``    -- seed, parameters and versions, for reproducibility;
* ``completion.png``   -- share of learners with all skills mastered (needs matplotlib).
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .bkt import BKTParams
from .simulation import DEFAULT_SKILLS, PROFILES, completion_curve, run_study, summarise


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_completion(results, max_steps: int, path: Path) -> bool:
    """Share of learners who completed all skills by task number, per profile.

    Returns False if matplotlib is not installed.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:  # pragma: no cover - exercised only without the plot extra
        return False

    # Categorical slots 1-3 of the validated palette; line style is a second cue,
    # and each curve is labelled directly, so identity never relies on colour alone.
    styles = {
        "slow": ("#2a78d6", "-"),
        "average": ("#eb6834", "--"),
        "fast": ("#1baf7a", ":"),
    }
    label_levels = {"fast": 0.85, "average": 0.70, "slow": 0.55}
    span = min(max_steps, max(r.steps for r in results) + 5)
    fig, ax = plt.subplots(figsize=(7.2, 4.0), dpi=150)
    ax.axhline(0.5, color="#bbbbbb", linewidth=1, linestyle=(0, (2, 2)), zorder=1)
    for name in PROFILES:
        curve = completion_curve(results, name, span)
        colour, dash = styles[name]
        ax.step(
            range(1, span + 1),
            curve,
            where="post",
            color=colour,
            linestyle=dash,
            linewidth=2,
            label=name,
            zorder=2,
        )
        half = next((t for t, share in enumerate(curve, start=1) if share >= 0.5), None)
        if half is not None:  # dot = median number of tasks for this profile
            ax.plot(
                half,
                0.5,
                "o",
                markersize=6,
                color=colour,
                zorder=3,
                markeredgecolor="white",
                markeredgewidth=1.5,
            )
        # Direct label to the left of the curve, each profile at its own height
        # so that the labels never touch a neighbouring curve.
        level = label_levels[name]
        at = next((t for t, share in enumerate(curve, start=1) if share >= level), None)
        if at is not None:
            ax.annotate(
                name,
                (at, level),
                xytext=(-6, 0),
                textcoords="offset points",
                ha="right",
                va="center",
                fontsize=10,
                color="#333333",
            )
    ax.text(
        span,
        0.52,
        "dots: median (half of learners)",
        fontsize=8.5,
        color="#666666",
        ha="right",
        va="bottom",
    )
    ax.set_xlim(0, span)
    ax.set_ylim(0, 1.03)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlabel("Task number")
    ax.set_ylabel("Learners with all skills mastered")
    ax.grid(axis="y", color="#e5e5e5", linewidth=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(title="Learner profile", frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ct-simulate",
        description="Simulate synthetic learners through the BKT + rules adaptive engine.",
    )
    parser.add_argument("--learners", type=int, default=50, help="learners per profile (50)")
    parser.add_argument("--max-steps", type=int, default=150, help="task limit per learner (150)")
    parser.add_argument("--seed", type=int, default=42, help="random seed (42)")
    parser.add_argument("--out", type=Path, default=Path("results"), help="output folder")
    parser.add_argument("--no-plot", action="store_true", help="skip the PNG figure")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.learners < 1 or args.max_steps < 1:
        print("error: --learners and --max-steps must be positive", file=sys.stderr)
        return 2

    results = run_study(args.learners, args.max_steps, args.seed)
    summary = summarise(results)
    args.out.mkdir(parents=True, exist_ok=True)

    interactions = [
        {"profile": r.profile, "learner_id": r.learner_id, **h} for r in results for h in r.history
    ]
    learners = [
        {
            "profile": r.profile,
            "learner_id": r.learner_id,
            "tasks": r.steps,
            "completed": r.completed,
            "false_mastery": r.false_mastery,
            "missed_mastery": r.missed_mastery,
        }
        for r in results
    ]
    _write_csv(args.out / "interactions.csv", interactions)
    _write_csv(args.out / "learners.csv", learners)
    _write_csv(args.out / "summary.csv", summary)

    metadata = {
        "package_version": __version__,
        "python": platform.python_version(),
        "seed": args.seed,
        "learners_per_profile": args.learners,
        "max_steps": args.max_steps,
        "skills": DEFAULT_SKILLS,
        "engine_params": asdict(BKTParams()),
        "learner_profiles": {k: asdict(v) for k, v in PROFILES.items()},
    }
    (args.out / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    if not args.no_plot:
        plot_completion(results, args.max_steps, args.out / "completion.png")

    print(f"{'profile':<10}{'completion':>12}{'median tasks':>15}{'false mastery':>15}")
    for row in summary:
        med = row["median_tasks_to_complete"]
        print(
            f"{row['profile']:<10}{row['completion_rate']:>12.0%}"
            f"{(med if med is not None else '-'):>15}{row['false_mastery_rate']:>15.1%}"
        )
    print(f"results written to {args.out}/")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
