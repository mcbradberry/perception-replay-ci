# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A proof-of-concept Robot CI regression test: replay a fixed `/scan` log through two versions of a perception stack (baseline vs. candidate) and automatically detect whether the candidate produces incorrect output. Open-loop — no robot motion during replay. Full spec in `demo_spec.md`.

## Stack

- ROS 2 Humble via RoboStack (conda channel `robostack-humble`)
- TurtleBot3 in Gazebo for sim and recording
- pixi for env + task running (osx-arm64 only — see `[workspace] platforms` in `pixi.toml`)
- Python perception nodes (`rclpy`), standalone scripts under `scripts/` — no colcon/ROS package
- MCAP-format rosbags

`TURTLEBOT3_MODEL=burger` is set via `[activation.env]` in `pixi.toml`, so every `pixi run` shell has it.

## Pixi tasks

| Task | Purpose |
|---|---|
| `sim` | Launch Gazebo + TurtleBot3 in `turtlebot3_world` |
| `control` | Keyboard teleop |
| `record` | Generic mcap recording of all topics into `run/` |
| `record-golden` | Record `/scan /tf /tf_static /odom` into `bags/golden_obstacle/` (the test fixture) |
| `baseline` | Run the baseline perception node |
| `candidate` | Run the (intentionally broken) candidate perception node |
| `record-run <path.jsonl>` | Subscribe to `/obstacle/{detected,range}` and append paired rows to JSONL |
| `compare` | Diff `runs/baseline.jsonl` vs `runs/candidate.jsonl`, print report; exits 1 on FAIL |

## End-to-end demo flow

Capture the fixture once (three shells):
1. `pixi run sim`
2. `pixi run record-golden`
3. `pixi run control` — drive near obstacles
4. Ctrl-C the recorder first so the mcap finalizes cleanly.

For each perception version (three shells per run):
1. `pixi run baseline` (or `candidate`)
2. `pixi run record-run runs/<name>.jsonl`
3. `pixi run -- ros2 bag play bags/golden_obstacle`
4. Ctrl-C the recorder when the bag finishes — lets it flush and log line count.

Then `pixi run compare`.

## Architecture notes that aren't obvious from the code

**Perception nodes intentionally duplicate.** `perception_baseline.py` and `perception_candidate.py` differ only in `DETECT_THRESHOLD_M` (0.50 vs 0.25). In real Robot CI, baseline and candidate are separately versioned implementations of the same interface — refactoring out a shared base would hide that they're meant to drift independently. Don't DRY this.

**Same output topics, run one at a time.** Both nodes publish to `/obstacle/detected` and `/obstacle/range`. The workflow runs the bag twice — once per node — never simultaneously. Mirrors how you'd A/B real perception stacks against the same input.

**Bool + stamped Range, paired by callback order.** `std_msgs/Bool` has no header, so timestamps live on the `sensor_msgs/Range` message (stamped from `scan.header.stamp`). `record_run.py` pairs them by "latest Bool when a Range arrives" — safe because both are published from the same scan callback in the perception node, in that order.

**Timestamps in JSONL are sim time, not wall time.** They come from the bag's recorded scan headers (Gazebo `/clock`), so values start around `~78s`, not a Unix epoch. The comparator only needs alignment between runs, which holds because both runs replay the same bag.

**QoS on `/scan` subscriptions must be `qos_profile_sensor_data`.** Default reliable QoS won't connect to either the LiDAR driver or `ros2 bag play` — both publish best-effort. The `/obstacle/*` topics use default reliable QoS.

**Baseline output is the ground truth.** The comparator flags any candidate disagreement as a regression. It does not detect *baseline* regressions; catching those would require hand-labeled expected windows.

## Layout

```
scripts/
  perception_baseline.py     reference detector (threshold 0.50m)
  perception_candidate.py    intentionally broken (threshold 0.25m)
  record_run.py              subscribes to /obstacle/* and writes JSONL
  compare_runs.py            diffs two JSONLs, prints report, exits 1 on FAIL
bags/golden_obstacle/        recorded test fixture (gitignored)
runs/                        JSONL outputs from record_run (gitignored)
demo_spec.md                 source-of-truth spec for what the demo proves
```
