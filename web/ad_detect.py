# # ad_detect.py
# from flask import Flask, render_template, request, redirect, url_for, session, flash

# from flask import Blueprint, render_template

# ad_detect_bp = Blueprint("ad_detect", __name__)

# @ad_detect_bp.route("/ad_detect")
# def ad_detect_page():
#     return render_template("ad_detect.html")
# # 2/4 개발 예정
# web/ad_detect.py  (너 프로젝트 경로에 맞춰 넣어줘)
import os
import threading
import time
import yaml
import math

from flask import Blueprint, render_template, jsonify

# ROS2
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped

ad_detect_bp = Blueprint("ad_detect", __name__)


MAP_YAML_PATH = "/home/rokey/Desktop/maps/map.yaml"
# map.yaml 안에 image: map.pgm 라고 되어있으니(:contentReference[oaicite:1]{index=1}),
# static에 png로 변환해서 올려두는 방식을 추천 (아래 2번 참고)
MAP_IMAGE_URL = "/static/map.png"

# 최신 포즈 저장소
_latest = {
    "robot1": {"x": None, "y": None, "yaw": None, "stamp": None},
    "robot3": {"x": None, "y": None, "yaw": None, "stamp": None},
}
_lock = threading.Lock()
_ros_started = False

def yaw_from_quaternion(q):
    """
    q: geometry_msgs.msg.Quaternion
    return: yaw (rad)
    """
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


def _load_map_meta():
    """map.yaml에서 resolution/origin 읽기"""
    with open(MAP_YAML_PATH, "r") as f:
        data = yaml.safe_load(f)
    resolution = float(data["resolution"])
    origin = data["origin"]  # [origin_x, origin_y, origin_yaw]
    return resolution, origin


class PoseListener(Node):
    def __init__(self):
        super().__init__("web_pose_listener")

        # =========================
        # ✅ TODO: 토픽 이름 맞는지 확인
        # =========================
        self.create_subscription(
            PoseWithCovarianceStamped,
            "/robot1/amcl_pose",   # TODO: 네 환경 토픽명
            self._cb_robot1,
            10,
        )
        self.create_subscription(
            PoseWithCovarianceStamped,
            "/robot3/amcl_pose",   # TODO: 네 환경 토픽명
            self._cb_robot3,
            10,
        )

    def _update(self, key: str, msg: PoseWithCovarianceStamped):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = yaw_from_quaternion(q)

        with _lock:
            _latest[key] = {
                "x": float(p.x),
                "y": float(p.y),
                "yaw": float(yaw),
                "stamp": time.time(),
            }

    def _cb_robot1(self, msg): self._update("robot1", msg)
    def _cb_robot3(self, msg): self._update("robot3", msg)


def _start_ros_thread_once():
    """Flask가 실행될 때 ROS2 스레드 1번만 시작"""
    global _ros_started
    if _ros_started:
        return
    _ros_started = True

    def _spin():
        rclpy.init(args=None)
        node = PoseListener()
        try:
            rclpy.spin(node)
        finally:
            node.destroy_node()
            rclpy.shutdown()

    t = threading.Thread(target=_spin, daemon=True)
    t.start()


@ad_detect_bp.route("/ad_detect")
def ad_detect_page():
    _start_ros_thread_once()

    resolution, origin = _load_map_meta()  # :contentReference[oaicite:2]{index=2} 참고
    # ✅ map 이미지 픽셀 크기는 프론트에서 이미지 로드 후 자동으로 얻어도 되지만,
    # 여기서는 템플릿에 meta만 넘기고, width/height는 JS가 이미지에서 읽게 할게.
    return render_template(
        "ad_detect.html",
        map_image_url=MAP_IMAGE_URL,
        map_resolution=resolution,
        map_origin=origin,  # [ox, oy, oyaw]
    )


@ad_detect_bp.route("/ad_detect/api/poses")
def ad_detect_api_poses():
    with _lock:
        return jsonify(_latest)
