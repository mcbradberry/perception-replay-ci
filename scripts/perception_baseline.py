#!/usr/bin/env python3
"""Baseline LaserScan obstacle detector.

Subscribes /scan, publishes /obstacle/detected (Bool) and /obstacle/range
(Range, stamped with the input scan's timestamp). Decision: obstacle is
present if the minimum valid range inside a forward angular wedge is below
DETECT_THRESHOLD_M.
"""

import math

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan, Range
from std_msgs.msg import Bool

FORWARD_HALF_ANGLE_DEG = 30.0
DETECT_THRESHOLD_M = 0.50


class PerceptionBaseline(Node):
    def __init__(self) -> None:
        super().__init__("perception_baseline")
        self._half_angle_rad = math.radians(FORWARD_HALF_ANGLE_DEG)
        self._threshold_m = DETECT_THRESHOLD_M

        self._sub = self.create_subscription(
            LaserScan, "/scan", self._on_scan, qos_profile_sensor_data
        )
        self._pub_detected = self.create_publisher(Bool, "/obstacle/detected", 10)
        self._pub_range = self.create_publisher(Range, "/obstacle/range", 10)

        self.get_logger().info(
            f"baseline up: wedge=±{FORWARD_HALF_ANGLE_DEG:.0f}°, "
            f"threshold={DETECT_THRESHOLD_M:.2f}m"
        )

    def _on_scan(self, scan: LaserScan) -> None:
        min_range = self._min_range_in_wedge(scan)
        detected = math.isfinite(min_range) and min_range < self._threshold_m

        self._pub_detected.publish(Bool(data=detected))

        range_msg = Range()
        range_msg.header = scan.header
        range_msg.radiation_type = Range.INFRARED
        range_msg.field_of_view = 2.0 * self._half_angle_rad
        range_msg.min_range = scan.range_min
        range_msg.max_range = scan.range_max
        range_msg.range = min_range if math.isfinite(min_range) else scan.range_max
        self._pub_range.publish(range_msg)

    def _min_range_in_wedge(self, scan: LaserScan) -> float:
        if scan.angle_increment == 0.0 or not scan.ranges:
            return math.inf

        min_val = math.inf
        for i, r in enumerate(scan.ranges):
            angle = scan.angle_min + i * scan.angle_increment
            # Wrap to [-pi, pi] so a 0-to-2pi scan still maps forward to 0.
            wrapped = math.atan2(math.sin(angle), math.cos(angle))
            if abs(wrapped) > self._half_angle_rad:
                continue
            if not math.isfinite(r):
                continue
            if r < scan.range_min or r > scan.range_max:
                continue
            if r < min_val:
                min_val = r
        return min_val


def main() -> None:
    rclpy.init()
    node = PerceptionBaseline()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
