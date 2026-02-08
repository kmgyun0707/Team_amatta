# web/ros_monitor.py
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import BatteryState
from geometry_msgs.msg import PoseWithCovarianceStamped
from my_robot_interfaces.msg import DetectionResult


@dataclass
class BatteryInfo:
    percent: float
    stamp: float  # time.time()


@dataclass
class PoseInfo:
    x: float
    y: float
    yaw: float
    stamp: float


class MonitorStore:
    """Flask에서 읽기 쉬운 형태로 메모리에 상태 저장 (thread-safe)"""
    def __init__(self, max_logs: int = 20):
        self._lock = threading.Lock()
        self.max_logs = max_logs

        self.db_post_logs: List[dict] = []   # 최근 20개
        self.battery: Dict[str, BatteryInfo] = {}  # robot1, robot3
        self.pose: Dict[str, PoseInfo] = {}        # robot1, robot3

    def push_db_post(self, item: dict):
        with self._lock:
            self.db_post_logs.append(item)
            if len(self.db_post_logs) > self.max_logs:
                self.db_post_logs = self.db_post_logs[-self.max_logs:]

    def set_battery(self, robot: str, percent: float):
        with self._lock:
            self.battery[robot] = BatteryInfo(percent=percent, stamp=time.time())

    def set_pose(self, robot: str, x: float, y: float, yaw: float):
        with self._lock:
            self.pose[robot] = PoseInfo(x=x, y=y, yaw=yaw, stamp=time.time())

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "db_post_logs": list(self.db_post_logs),
                "battery": {k: {"percent": v.percent, "stamp": v.stamp} for k, v in self.battery.items()},
                "pose": {k: {"x": v.x, "y": v.y, "yaw": v.yaw, "stamp": v.stamp} for k, v in self.pose.items()},
            }


def _yaw_from_quat(q) -> float:
    # geometry_msgs/Quaternion -> yaw
    # yaw = atan2(2*(w*z + x*y), 1 - 2*(y*y + z*z))
    import math
    w, x, y, z = q.w, q.x, q.y, q.z
    return math.atan2(2.0*(w*z + x*y), 1.0 - 2.0*(y*y + z*z))


class RosMonitorNode(Node):
    def __init__(self, store: MonitorStore):
        super().__init__("ad_ros_monitor")
        self.store = store

        # /db_post (DetectionResult)
        self.create_subscription(DetectionResult, "/db_post", self._on_db_post, 10)

        # 배터리
        self.create_subscription(BatteryState, "/robot1/battery_state", lambda m: self._on_batt("robot1", m), 10)
        self.create_subscription(BatteryState, "/robot3/battery_state", lambda m: self._on_batt("robot3", m), 10)

        # 위치 (amcl_pose)
        self.create_subscription(PoseWithCovarianceStamped, "/robot1/amcl_pose", lambda m: self._on_pose("robot1", m), 10)
        self.create_subscription(PoseWithCovarianceStamped, "/robot3/amcl_pose", lambda m: self._on_pose("robot3", m), 10)

        self.get_logger().info("✅ RosMonitorNode started: /db_post, battery_state, amcl_pose")

    def _on_db_post(self, msg: DetectionResult):
        try:
            x = float(msg.pose.pose.position.x)
            y = float(msg.pose.pose.position.y)
        except Exception:
            x, y = 0.0, 0.0

        item = {
            "stamp": time.time(),
            "class_name": (msg.class_name or "").strip(),
            "ns": (msg.ns or "").strip(),
            "x": x,
            "y": y,
        }
        self.store.push_db_post(item)

    def _on_batt(self, robot: str, msg: BatteryState):
        # BatteryState.percentage는 0~1 일 때가 많음. (드라이버에 따라 0~100도 있음)
        p = float(msg.percentage)
        if p <= 1.0:
            p *= 100.0
        p = max(0.0, min(p, 100.0))
        self.store.set_battery(robot, p)

    def _on_pose(self, robot: str, msg: PoseWithCovarianceStamped):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = _yaw_from_quat(q)
        self.store.set_pose(robot, float(p.x), float(p.y), float(yaw))


class RosMonitorRunner:
    """Flask 프로세스 안에서 ROS2를 백그라운드로 돌리기 위한 러너"""
    def __init__(self, store: MonitorStore):
        self.store = store
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        rclpy.init(args=None)
        node = RosMonitorNode(self.store)
        try:
            rclpy.spin(node)
        except Exception:
            pass
        finally:
            node.destroy_node()
            rclpy.shutdown()
