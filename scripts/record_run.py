#!/usr/bin/env python3
"""Record one perception run to a JSONL file.

Subscribes to /obstacle/detected and /obstacle/range. For each Range
message, writes a JSONL row keyed by the scan's original timestamp:

    {"t": 1778698930.858, "detected": true, "min_range": 0.42}

Detected is paired by latest-Bool — the perception nodes publish Bool
then Range in the same callback, so the most recent Bool when a Range
arrives belongs to that scan.
"""

import json
import sys
from pathlib import Path

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Range
from std_msgs.msg import Bool


class RunRecorder(Node):
    def __init__(self, out_path: Path) -> None:
        super().__init__("run_recorder")
        self._out = out_path.open("w", buffering=1)  # line-buffered
        self._last_detected: bool | None = None
        self._count = 0

        self.create_subscription(Bool, "/obstacle/detected", self._on_detected, 10)
        self.create_subscription(Range, "/obstacle/range", self._on_range, 10)

        self.get_logger().info(f"recording to {out_path}")

    def _on_detected(self, msg: Bool) -> None:
        self._last_detected = msg.data

    def _on_range(self, msg: Range) -> None:
        if self._last_detected is None:
            return  # haven't seen the paired Bool yet, drop this scan
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        line = json.dumps(
            {"t": t, "detected": self._last_detected, "min_range": msg.range}
        )
        self._out.write(line + "\n")
        self._count += 1

    def close(self) -> None:
        self._out.close()
        self.get_logger().info(f"wrote {self._count} lines")


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: record_run.py <output.jsonl>", file=sys.stderr)
        sys.exit(2)
    out_path = Path(sys.argv[1])
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rclpy.init()
    node = RunRecorder(out_path)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
