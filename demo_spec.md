# Robot CI LaserScan Perception Replay Demo Spec

## Goal

Build a proof-of-concept open-loop robot regression test using ROS 2, TurtleBot3, Gazebo, rosbag/MCAP replay, and a simple LaserScan-based perception node.

The demo should prove this core Robot CI idea:

> Given the same recorded robot sensor log, can we replay it through two versions of a perception stack and automatically detect whether the candidate version produces an incorrect output?

This is an open-loop replay test. The robot does not need to move based on the perception node’s output. The goal is to replay fixed recorded sensor data and evaluate whether the perception output is correct.

---

## High-Level Demo Story

1. Run a TurtleBot3 simulation in Gazebo.
2. Drive the TurtleBot3 near an obstacle.
3. Record the robot’s `/scan` topic into a ROS 2 bag using MCAP storage.
4. Run a baseline perception node that correctly detects an obstacle.
5. Replay the same `/scan` log through the baseline node and record its output.
6. Run a candidate/broken perception node that fails to detect the obstacle.
7. Replay the same `/scan` log through the candidate node and record its output.
8. Compare candidate output against baseline output or expected ground truth.
9. Generate a pass/fail result and simple report.

The demo should produce output like:

```text
Test: turtlebot3_laserscan_obstacle_regression
Result: FAIL

Reason:
- Expected obstacle_detected=true between 12.0s and 18.0s
- Candidate failed to detect obstacle for 5.4 seconds
- Minimum observed distance was 0.42m, but candidate threshold was 0.25m

Recommendation:
Do not deploy candidate perception config.
