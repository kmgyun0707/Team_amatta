# 예상치 못한 분실물을 발견했을 때 그 분실물에 대한 정보를 item 테이블에 저장하는 파일

import os
import json
import base64
import uuid
import sqlite3
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String  # JSON을 String에 담아 받는 방식

DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"
UPLOAD_DIR = "/home/rokey/Desktop/amatta/static"
TOPIC_NAME = "/found_item"  # 로봇이 publish 하는 토픽 이름

os.makedirs(UPLOAD_DIR, exist_ok=True)
_db_lock = threading.Lock()

def save_base64_image_to_file(image_b64: str) -> str:
    """data:image/...;base64,... 또는 순수 base64 모두 처리해서 파일로 저장 후 image_path 리턴"""
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]

    data = base64.b64decode(image_b64)
    filename = f"{uuid.uuid4().hex}.jpg"
    abs_path = os.path.join(UPLOAD_DIR, filename)
    with open(abs_path, "wb") as f:
        f.write(data)

    return f"/static/{filename}"

def insert_item(category: str, color: str, x: float, y: float,
                image_path: str | None = None):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # ✅ state는 DEFAULT '보관중' 이므로 생략 가능
        cur.execute("""
            INSERT INTO item (category, color, location_x, location_y, image_path)
            VALUES (?, ?, ?, ?, ?)
        """, (category, color, float(x), float(y), image_path))

        conn.commit()
        conn.close()

class FoundItemSubscriber(Node):
    def __init__(self):
        super().__init__("found_item_subscriber")
        self.sub = self.create_subscription(String, TOPIC_NAME, self.cb, 10)
        self.get_logger().info(f"✅ Listening: {TOPIC_NAME}")

    def cb(self, msg: String):
        try:
            payload = json.loads(msg.data)

            category = (payload.get("category") or "").strip()
            color = (payload.get("color") or "").strip()
            x = payload.get("location_x")
            y = payload.get("location_y")

            # 필수값 체크
            if not category or x is None or y is None:
                self.get_logger().warn(f"⚠️ missing required fields: {payload}")
                return

            # 이미지 처리: base64가 오면 (1)파일로 저장해서 image_path 넣고,
            #            옵션으로 (2)BLOB에도 넣을 수 있음
            image_path = None

            image_b64 = payload.get("image_base64")
            if image_b64:
                # ✅ 추천: 파일 저장 + 경로 저장
                image_path = save_base64_image_to_file(image_b64)

                # ✅ 원하면 BLOB도 함께 저장(옵션)
                if image_b64:
                    image_path = save_base64_image_to_file(image_b64)
                elif payload.get("image_path"):
                    image_path = (payload.get("image_path") or "").strip()

            insert_item(category, color, x, y, image_path=image_path)
            self.get_logger().info(f"✅ INSERT OK: {category} / {color} @({x},{y})")

        except Exception as e:
            self.get_logger().error(f"❌ failed: {e} | raw={msg.data[:200]}")

def start_found_item_listener():
    """Flask 실행 시 1번 호출해서 백그라운드 구독 시작"""
    rclpy.init()
    node = FoundItemSubscriber()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
