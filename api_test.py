# DetectionResult를 받아 item 테이블에 저장
# + GPT 비전으로 색상 추출 (한글 저장)
# + 이미지 파일명: item_{id}.png 형식으로 저장

import os
import sqlite3
import threading
import queue
import base64
import re
from typing import Optional, Tuple

import rclpy
from rclpy.node import Node

from cv_bridge import CvBridge
import cv2
import numpy as np

from my_robot_interfaces.msg import DetectionResult


DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"
UPLOAD_DIR = "/home/rokey/Desktop/amatta/static"
TOPIC_NAME = "/db_post"

os.makedirs(UPLOAD_DIR, exist_ok=True)

_db_lock = threading.Lock()
_bridge = CvBridge()

USE_GPT_COLOR = os.getenv("USE_GPT_COLOR", "0").strip() in ("1", "true", "True")
OPENAI_API_KEY = os.getenv("", "").strip()

_gpt_queue: "queue.Queue[Tuple[int, np.ndarray]]" = queue.Queue(maxsize=50)
_stop_event = threading.Event()


# =========================
# pose → x,y
# =========================
def get_xy_from_pose(pose_msg) -> Tuple[float, float]:
    try:
        return float(pose_msg.pose.position.x), float(pose_msg.pose.position.y)
    except Exception:
        return 0.0, 0.0


# =========================
# DB 함수
# =========================
def insert_item_return_id(category, color, robot_ns, x, y) -> int:
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO item (category, color, robot_name, location_x, location_y)
            VALUES (?, ?, ?, ?, ?)
            """,
            (category, color, robot_ns, x, y),
        )
        item_id = cur.lastrowid
        conn.commit()
        conn.close()
        return item_id


def update_item_image_path(item_id, image_path):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE item SET image_path=? WHERE id=?", (image_path, item_id))
        conn.commit()
        conn.close()


def update_item_color(item_id, color):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE item SET color=? WHERE id=?", (color, item_id))
        conn.commit()
        conn.close()


# =========================
# 색상 정규화 (한글 저장)
# =========================
def normalize_color_to_korean(raw: str) -> str:
    if not raw:
        return "알수없음"

    s = str(raw).strip()
    s = re.split(r"[,\n\.]", s, maxsplit=1)[0]
    s = s.replace('"', "").replace("'", "").strip()

    if not s:
        return "알수없음"

    return s


# =========================
# GPT 색상 추출
# =========================
def extract_color_with_gpt(cv_img):
    if not OPENAI_API_KEY:
        return "알수없음"

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    ok, buf = cv2.imencode(".png", cv_img)
    if not ok:
        return "알수없음"

    b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
    data_url = f"data:image/png;base64,{b64}"

    prompt = (
        "이 이미지 속 물체의 대표 색상 1개를 한글로 말해줘.\n"
        "설명 없이 JSON만 반환.\n"
        '형식: {"color":"한글색상"}'
    )

    try:
        resp = client.responses.create(
            model="gpt-4o-mini",
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url},
                ],
            }],
        )

        out = resp.output_text.strip()
        import json
        color = json.loads(out).get("color", "")
        return normalize_color_to_korean(color)

    except Exception:
        return "알수없음"


def gpt_worker():
    while not _stop_event.is_set():
        try:
            item_id, cv_img = _gpt_queue.get(timeout=0.2)
        except queue.Empty:
            continue

        color = extract_color_with_gpt(cv_img)
        if not color:
            color = "알수없음"

        update_item_color(item_id, color)
        _gpt_queue.task_done()


# =========================
# ROS2 Node
# =========================
class FoundItemSubscriber(Node):
    def __init__(self):
        super().__init__("found_item_subscriber")
        self.sub = self.create_subscription(
            DetectionResult, TOPIC_NAME, self.cb, 10
        )

        self.get_logger().info("Listening /db_post")

        if USE_GPT_COLOR and OPENAI_API_KEY:
            threading.Thread(target=gpt_worker, daemon=True).start()

    def cb(self, msg: DetectionResult):
        try:
            category = msg.class_name.strip()
            robot_ns = msg.ns.strip() if msg.ns else "unknown_robot"
            x, y = get_xy_from_pose(msg.pose)

            cv_img = _bridge.imgmsg_to_cv2(msg.image, desired_encoding="bgr8")

            # 1️⃣ 먼저 INSERT → id 확보
            item_id = insert_item_return_id(
                category,
                "추출중" if USE_GPT_COLOR else "알수없음",
                robot_ns,
                x,
                y,
            )

            # 2️⃣ 이미지 파일명: item_{id}.png
            filename = f"item_{item_id}.png"
            abs_path = os.path.join(UPLOAD_DIR, filename)
            cv2.imwrite(abs_path, cv_img)

            image_path = f"/static/{filename}"
            update_item_image_path(item_id, image_path)

            # 3️⃣ GPT 색상 추출
            if USE_GPT_COLOR and OPENAI_API_KEY:
                _gpt_queue.put((item_id, cv_img))
            else:
                update_item_color(item_id, "알수없음")

            self.get_logger().info(f"✅ 저장 완료 id={item_id}")

        except Exception as e:
            self.get_logger().error(f"❌ 실패: {e}")


def main():
    rclpy.init()
    node = FoundItemSubscriber()
    try:
        rclpy.spin(node)
    finally:
        _stop_event.set()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
