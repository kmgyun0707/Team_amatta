#!/usr/bin/env python3
# DetectionResult를 받아 item 테이블에 저장
# + OpenAI Responses API(새 방식)로 색상 추출 (한글 저장)
# + 이미지 파일명: item_{id}.png 형식으로 저장

import os
import sqlite3
import threading
import queue
import base64
import re
import json
from typing import Tuple

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

# ✅ USE_GPT_COLOR=1 / true면 GPT로 색상 추출
USE_GPT_COLOR = os.getenv("USE_GPT_COLOR", "0").strip().lower() in ("1", "true")

# ✅ 새 방식: OpenAI()가 OPENAI_API_KEY 환경변수 자동 사용
#    (키를 코드에서 직접 getenv로 읽지 않아도 됨)
_client = None
if USE_GPT_COLOR:
    try:
        from openai import OpenAI
        _client = OpenAI()
    except Exception:
        _client = None

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
    # 첫 줄/첫 단어만
    s = re.split(r"[\n,\.]", s, maxsplit=1)[0]
    s = s.replace('"', "").replace("'", "").strip()

    if not s:
        return "알수없음"

    return s


# =========================
# GPT 색상 추출 (새 방식)
# =========================
def extract_color_with_gpt(cv_img: np.ndarray) -> str:
    # GPT 사용 OFF or 클라이언트 준비 실패면 종료
    if not USE_GPT_COLOR or _client is None:
        return "알수없음"

    ok, buf = cv2.imencode(".png", cv_img)
    if not ok:
        return "알수없음"

    b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
    data_url = f"data:image/png;base64,{b64}"

    prompt = (
        "이 이미지 속 물체의 대표 색상 1개를 한글로만 답해줘.\n"
        "설명 없이 JSON만 반환해.\n"
        '형식: {"color":"한글색상"}'
    )

    try:
        resp = _client.responses.create(
            # ✅ 이미지 분석은 이 모델이 안정적
            model="gpt-4o-mini",
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url},
                ],
            }],
        )

        out = (resp.output_text or "").strip()

        # 모델이 가끔 ```json ...``` 감싸면 제거
        out = out.strip()
        out = re.sub(r"^```(?:json)?\s*", "", out)
        out = re.sub(r"\s*```$", "", out).strip()

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

        self.get_logger().info(f"Listening {TOPIC_NAME} (DetectionResult)")

        # ✅ GPT ON + OpenAI 클라이언트 준비됐을 때만 워커 시작
        if USE_GPT_COLOR and _client is not None:
            threading.Thread(target=gpt_worker, daemon=True).start()
            self.get_logger().info("GPT color extraction: ON")
        else:
            self.get_logger().info("GPT color extraction: OFF")

    def cb(self, msg: DetectionResult):
        try:
            category = (msg.class_name or "").strip() or "알수없음"
            robot_ns = (msg.ns or "").strip() or "unknown_robot"
            x, y = get_xy_from_pose(msg.pose)

            cv_img = _bridge.imgmsg_to_cv2(msg.image, desired_encoding="bgr8")

            # 1) 먼저 INSERT → id 확보
            item_id = insert_item_return_id(
                category,
                "추출중" if (USE_GPT_COLOR and _client is not None) else "알수없음",
                robot_ns,
                x,
                y,
            )

            # 2) 이미지 파일명: item_{id}.png
            filename = f"item_{item_id}.png"
            abs_path = os.path.join(UPLOAD_DIR, filename)
            cv2.imwrite(abs_path, cv_img)

            image_path = f"/static/{filename}"
            update_item_image_path(item_id, image_path)

            # 3) GPT 색상 추출 (비동기)
            if USE_GPT_COLOR and _client is not None:
                try:
                    _gpt_queue.put_nowait((item_id, cv_img))
                except queue.Full:
                    # 큐가 꽉 차면 색상 스킵 (콜백이 멈추지 않게)
                    update_item_color(item_id, "알수없음")
                    self.get_logger().warn("GPT queue full -> color skip")
            else:
                update_item_color(item_id, "알수없음")

            self.get_logger().info(f"✅ 저장 완료 id={item_id}, file={filename}")

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
