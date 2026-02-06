import os
import threading
import time
import yaml
import math
import cv2
import numpy as np

from flask import Blueprint, render_template, jsonify, Response
from sensor_msgs.msg import Image
from geometry_msgs.msg import PoseWithCovarianceStamped
from cv_bridge import CvBridge

# ROS2 Libraries
import rclpy
from rclpy.node import Node
# qos_profile_sensor_data는 지우고 기본 설정(10)을 사용합니다.

ad_detect_bp = Blueprint("ad_detect", __name__)
bridge = CvBridge()
_lock = threading.Lock()

# ==========================================
# ✅ 설정 및 전역 변수
# ==========================================
MAP_YAML_PATH = "/home/rokey/Desktop/amatta/map.yaml"
MAP_IMAGE_URL = "/static/map.png"

# 데이터 저장소
_frames = {
    "robot1": None,
    "robot3": None
}
_latest_pose = {
    "robot1": {"x": None, "y": None, "yaw": None},
    "robot3": {"x": None, "y": None, "yaw": None},
}
# 디버깅 상태
_robot_status = {
    "robot1": {"last_img_time": 0, "img_count": 0, "img_size": "waiting..."},
    "robot3": {"last_img_time": 0, "img_count": 0, "img_size": "waiting..."},
}

_ros_started = False

def yaw_from_quaternion(q):
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)

def _load_map_meta():
    if not os.path.exists(MAP_YAML_PATH): return 0.05, [0, 0, 0]
    with open(MAP_YAML_PATH, "r") as f:
        data = yaml.safe_load(f)
    return float(data["resolution"]), data["origin"]

# ==========================================
# ✅ ROS 2 Node Class (설정 수정됨)
# ==========================================
class AdDetectListener(Node):
    def __init__(self):
        super().__init__("web_ad_detect_node")

        # 👇 [핵심 수정] 
        # 1. 토픽 이름: image_raw (소문자) 확인됨
        # 2. QoS: rosbag은 RELIABLE이므로 숫자 '10' 사용
        self.create_subscription(
            Image, 
            "/robot1/oakd/rgb/image_raw", 
            self._cb_img_robot1, 
            10  # ✅ RELIABLE 모드 (rosbag 재생 시 필수)
        )
        self.create_subscription(
            Image, 
            "/robot3/oakd/rgb/image_raw", 
            self._cb_img_robot3, 
            10  # ✅ RELIABLE 모드
        )

        self.create_subscription(PoseWithCovarianceStamped, "/robot1/amcl_pose", self._cb_pose_robot1, 10)
        self.create_subscription(PoseWithCovarianceStamped, "/robot3/amcl_pose", self._cb_pose_robot3, 10)

    def _cb_img_robot1(self, msg): self._process_img("robot1", msg)
    def _cb_img_robot3(self, msg): self._process_img("robot3", msg)

    def _process_img(self, robot_id, msg):
        # ✅ 터미널 로그: 이게 뜨면 성공입니다.
        print(f"[{robot_id}] Image Received! ({msg.width}x{msg.height})")
        
        try:
            with _lock:
                _robot_status[robot_id]["last_img_time"] = time.time()
                _robot_status[robot_id]["img_count"] += 1
                _robot_status[robot_id]["img_size"] = f"{msg.width}x{msg.height}"

            # 이미지 변환
            cv_img = bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            _, buffer = cv2.imencode('.jpg', cv_img)
            with _lock:
                _frames[robot_id] = buffer.tobytes()
                
        except Exception as e:
            self.get_logger().error(f"Image Convert Error ({robot_id}): {e}")

    def _cb_pose_robot1(self, msg): self._process_pose("robot1", msg)
    def _cb_pose_robot3(self, msg): self._process_pose("robot3", msg)

    def _process_pose(self, robot_id, msg):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        with _lock:
            _latest_pose[robot_id] = {
                "x": float(p.x), "y": float(p.y), "yaw": yaw_from_quaternion(q)
            }

def start_ros_thread():
    global _ros_started
    if _ros_started: return
    _ros_started = True
    def _spin():
        rclpy.init(args=None)
        node = AdDetectListener()
        print("✅ ROS 2 Node Started. Waiting for topics...")
        try:
            rclpy.spin(node)
        finally:
            node.destroy_node()
            rclpy.shutdown()
    threading.Thread(target=_spin, daemon=True).start()

def gen_frames(robot_id):
    while True:
        with _lock:
            frame_data = _frames.get(robot_id)
        if frame_data:
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
        else:
            time.sleep(0.1)
        # bag 파일 속도가 느리므로(0.4hz) 딜레이를 넉넉히 줌
        time.sleep(0.1)

@ad_detect_bp.route("/ad_detect")
def ad_detect_page():
    start_ros_thread()
    res, origin = _load_map_meta()
    return render_template("ad_detect.html", map_image_url=MAP_IMAGE_URL, map_resolution=res, map_origin=origin)

@ad_detect_bp.route("/ad_detect/api/poses")
def api_poses():
    with _lock: return jsonify(_latest_pose)

@ad_detect_bp.route("/ad_detect/api/status")
def api_status():
    current_time = time.time()
    with _lock:
        status_copy = {}
        for rid, info in _robot_status.items():
            # 마지막 수신 시간이 5초 이내면 연결된 것으로 간주 (bag 파일이 느려서 5초로 늘림)
            diff = current_time - info["last_img_time"] if info["last_img_time"] > 0 else -1
            status_copy[rid] = {
                "connected": diff < 5.0 and diff != -1, 
                "ago": round(diff, 1),
                "count": info["img_count"],
                "size": info["img_size"]
            }
        return jsonify(status_copy)

@ad_detect_bp.route("/ad_detect/video_feed/<robot_id>")
def video_feed(robot_id):
    return Response(gen_frames(robot_id), mimetype='multipart/x-mixed-replace; boundary=frame')