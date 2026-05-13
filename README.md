# perception-replay-ci

A proof-of-concept Robot CI regression test. Replay a recorded `/scan` log through two versions of a perception stack (baseline vs. candidate) and automatically detect whether the candidate produces incorrect output.

The thesis: **given the same recorded robot sensor log, can we replay it through two versions of a perception stack and automatically catch a regression in the candidate?**

This is *open-loop replay testing* — the robot does not move during the test. The bag is the fixture, the perception nodes are the unit under test, and the comparator decides pass/fail. Full spec in [`demo_spec.md`](demo_spec.md).

## Stack

- ROS 2 Humble via [RoboStack](https://robostack.github.io/) (`robostack-humble` conda channel)
- TurtleBot3 in Gazebo for capturing the test fixture
- MCAP-format rosbags
- Python perception nodes (`rclpy`)
- [pixi](https://pixi.sh) for environment + tasks

Currently `osx-arm64` only (see `[workspace] platforms` in `pixi.toml`).

## Install

```sh
pixi install
```

This pulls the full ROS Humble desktop, TurtleBot3 packages, and the MCAP storage plugin.

## End-to-end demo

### 1. Capture the golden bag (one time)

Three shells:

```sh
pixi run sim                # Gazebo + TurtleBot3 in turtlebot3_world
pixi run record-golden      # records /scan /tf /tf_static /odom to bags/golden_obstacle/
pixi run control            # teleop keyboard — drive toward obstacles
```

Drive forward, approach an obstacle until the front of `/scan` reads ~0.4–0.5 m, hold, back off, repeat for a second obstacle if you like. Ctrl-C the recorder first when done so the MCAP finalizes cleanly.

### 2. Replay the bag through each perception version

For each version, three shells:

```sh
pixi run baseline                                # or `candidate`
pixi run record-run runs/baseline.jsonl          # or runs/candidate.jsonl
pixi run -- ros2 bag play bags/golden_obstacle
```

When the bag finishes, Ctrl-C the recorder (it'll log the line count).

### 3. Compare

```sh
pixi run compare
```

Exits 0 on PASS, 1 on FAIL — CI-friendly.

Example FAIL output:

```text
Test: turtlebot3_laserscan_obstacle_regression
Result: FAIL

Reason:
- Candidate failed to detect obstacle for 16.2s across 4 window(s)
- Minimum observed distance during misses: 0.25m

Disagreement windows:
     99.75s →   108.55s ( 8.80s, n= 45, min_range=0.31m): miss
    123.15s →   127.55s ( 4.40s, n= 23, min_range=0.25m): miss
    127.95s →   130.35s ( 2.40s, n= 13, min_range=0.25m): miss
    131.15s →   131.75s ( 0.60s, n=  4, min_range=0.27m): miss

Recommendation:
Do not deploy candidate perception config.
```

## How it works

Both perception nodes subscribe to `/scan`, find the minimum range in a forward ±30° wedge, and publish:

- `/obstacle/detected` (`std_msgs/Bool`) — fired when min range < threshold
- `/obstacle/range` (`sensor_msgs/Range`, stamped with the scan's original timestamp)

The baseline uses a 0.50 m threshold; the candidate uses 0.25 m (the intentional defect). Both publish to the *same* topics — the workflow runs the bag twice, once per node, never simultaneously.

`record_run.py` taps both topics during a replay and writes one JSONL row per scan: `{"t": <scan stamp>, "detected": bool, "min_range": float}`.

`compare_runs.py` reads two JSONL files, pairs rows by index (timestamps are identical across runs because both come from the same bag), groups disagreements into contiguous windows, classifies them as `miss` (baseline=true, candidate=false) or `false_alarm` (the inverse), and emits the pass/fail report.

## Layout

```
scripts/
  perception_baseline.py     reference detector (threshold 0.50m)
  perception_candidate.py    intentionally broken (threshold 0.25m)
  record_run.py              subscribes to /obstacle/* and writes JSONL
  compare_runs.py            diffs two JSONLs, prints report, exits 1 on FAIL
bags/golden_obstacle/        recorded test fixture (gitignored)
runs/                        JSONL outputs from record_run (gitignored)
demo_spec.md                 source-of-truth spec
```

## Why baseline-as-ground-truth?

The comparator treats the baseline's output as ground truth — any candidate disagreement is a regression. This mirrors real Robot CI patterns where the production version is the reference and you're guarding against breakage in a candidate. It does *not* catch regressions in the baseline itself; that would require hand-labeled expected windows.
