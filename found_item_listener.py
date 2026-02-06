# # 예상치 못한 분실물을 발견했을 때 그 분실물에 대한 정보를 item 테이블에 저장하는 파일
import os
import uuid
import sqlite3
import threading

import rclpy
from rclpy.node import Node

from cv_bridge import CvBridge
import cv2

from my_robot_interfaces.msg import DetectionResult

DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"
UPLOAD_DIR = "/home/rokey/Desktop/amatta/static"
TOPIC_NAME = "/db_post"

os.makedirs(UPLOAD_DIR, exist_ok=True)
_db_lock = threading.Lock()

_bridge = CvBridge()

def save_image_msg_to_file(image_msg) -> str:
    """sensor_msgs/Image -> jpg 저장 -> /static/xxx.jpg 리턴"""
    cv_img = _bridge.imgmsg_to_cv2(image_msg, desired_encoding="bgr8")
    filename = f"{uuid.uuid4().hex}.png"
    abs_path = os.path.join(UPLOAD_DIR, filename)
    cv2.imwrite(abs_path, cv_img)
    return f"/static/{filename}"

def insert_item(category: str, color: str, robot_ns: str, x: float, y: float, image_path: str | None = None):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO item (category, color, robot_name, location_x, location_y, image_path)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (category, color, robot_ns, float(x), float(y), image_path))
        conn.commit()
        conn.close()

class FoundItemSubscriber(Node):
    def __init__(self):
        super().__init__("found_item_subscriber")
        self.sub = self.create_subscription(DetectionResult, TOPIC_NAME, self.cb, 10)
        self.get_logger().info(f"✅ Listening: {TOPIC_NAME} ({DetectionResult.__name__})")

    def cb(self, msg: DetectionResult):
        try:
            category = (msg.class_name or "").strip()
            if not category:
                self.get_logger().warn("⚠️ class_name empty")
                return

            # pose -> x,y
            x = msg.pose.pose.position.x
            y = msg.pose.pose.position.y

            # color (msg에 없으면 기본값)
            color = getattr(msg, "color", "") or "unknown"
            robot_ns = getattr(msg, "ns", "") or "unknown_robot"

            # image 저장
            image_path = None
            if msg.image.data:  # 이미지가 비어있지 않으면
                image_path = save_image_msg_to_file(msg.image)

            insert_item(category, color, robot_ns, x, y, image_path=image_path)
            self.get_logger().info(f"✅ INSERT OK: {category} / {color} @({x:.2f},{y:.2f}) img={image_path}")

        except Exception as e:
            self.get_logger().error(f"❌ failed: {e}")

def main():
    rclpy.init()
    node = FoundItemSubscriber()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
