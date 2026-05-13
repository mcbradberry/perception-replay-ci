#!/usr/bin/env python3
"""Compare a candidate perception run against the baseline run.

Baseline output is treated as ground truth. Any sample where the
candidate's `detected` flag disagrees with the baseline's is a
regression. Disagreements are grouped into contiguous windows and
classified as:

    miss        baseline=True,  candidate=False  (dangerous — missed obstacle)
    false_alarm baseline=False, candidate=True   (less dangerous — phantom)

Exits 0 on PASS, 1 on FAIL.
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Sample:
    t: float
    detected: bool
    min_range: float


@dataclass
class Window:
    start_t: float
    end_t: float
    direction: str  # "miss" | "false_alarm"
    min_range: float = float("inf")
    n_samples: int = 0

    @property
    def duration(self) -> float:
        return self.end_t - self.start_t


def load(path: Path) -> list[Sample]:
    out: list[Sample] = []
    with path.open() as f:
        for line in f:
            row = json.loads(line)
            out.append(Sample(row["t"], row["detected"], row["min_range"]))
    return out


def find_windows(baseline: list[Sample], candidate: list[Sample]) -> list[Window]:
    windows: list[Window] = []
    cur: Window | None = None

    for b, c in zip(baseline, candidate):
        if abs(b.t - c.t) > 1e-3:
            print(
                f"WARN: timestamp mismatch baseline={b.t:.3f} candidate={c.t:.3f}",
                file=sys.stderr,
            )

        if b.detected == c.detected:
            if cur is not None:
                windows.append(cur)
                cur = None
            continue

        direction = "miss" if b.detected else "false_alarm"
        sample_min = min(b.min_range, c.min_range)

        if cur is None or cur.direction != direction:
            if cur is not None:
                windows.append(cur)
            cur = Window(start_t=b.t, end_t=b.t, direction=direction)

        cur.end_t = b.t
        cur.min_range = min(cur.min_range, sample_min)
        cur.n_samples += 1

    if cur is not None:
        windows.append(cur)
    return windows


def print_report(
    baseline: list[Sample], candidate: list[Sample], windows: list[Window]
) -> str:
    misses = [w for w in windows if w.direction == "miss"]
    false_alarms = [w for w in windows if w.direction == "false_alarm"]
    miss_duration = sum(w.duration for w in misses)
    fa_duration = sum(w.duration for w in false_alarms)

    result = "PASS" if not windows else "FAIL"

    print("Test: turtlebot3_laserscan_obstacle_regression")
    print(f"Result: {result}")
    print()

    if not windows:
        print("Reason:")
        print(f"- Candidate matched baseline on all {len(baseline)} samples")
        return result

    print("Reason:")
    if misses:
        min_in_misses = min(w.min_range for w in misses)
        print(
            f"- Candidate failed to detect obstacle for {miss_duration:.1f}s "
            f"across {len(misses)} window(s)"
        )
        print(f"- Minimum observed distance during misses: {min_in_misses:.2f}m")
    if false_alarms:
        print(
            f"- Candidate false-alarmed for {fa_duration:.1f}s "
            f"across {len(false_alarms)} window(s)"
        )

    print()
    print("Disagreement windows:")
    for w in windows:
        label = "miss" if w.direction == "miss" else "false_alarm"
        print(
            f"  {w.start_t:8.2f}s → {w.end_t:8.2f}s "
            f"({w.duration:5.2f}s, n={w.n_samples:3d}, "
            f"min_range={w.min_range:.2f}m): {label}"
        )

    print()
    print("Recommendation:")
    print("Do not deploy candidate perception config.")
    return result


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: compare_runs.py <baseline.jsonl> <candidate.jsonl>",
            file=sys.stderr,
        )
        return 2

    baseline = load(Path(sys.argv[1]))
    candidate = load(Path(sys.argv[2]))

    if len(baseline) != len(candidate):
        print(
            f"WARN: sample-count mismatch baseline={len(baseline)} "
            f"candidate={len(candidate)} — comparing the overlap",
            file=sys.stderr,
        )

    windows = find_windows(baseline, candidate)
    result = print_report(baseline, candidate, windows)
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
