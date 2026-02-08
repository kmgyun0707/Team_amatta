"""
실행방법
1) export USE_GPT_COLOR=1
2) export OPEN_API_KEY="키 값"
3) python3 api_test.py

이 파일은 ROS2 노드로 실행되며, 로봇이 보내는 DetectionResult 메시지를 받아서:

1) item 테이블에 "새 아이템 1건"을 INSERT 한다.
   - category(물체 종류), robot_name(로봇 이름/namespace), 위치(x,y), color(처음엔 '추출중' 또는 '알수없음')

2) 메시지에 들어있는 이미지(sensor_msgs/Image)를 파일로 저장한다.
   - 저장 파일명 규칙: item_{id}.png  (예: item_21.png)
   - 웹에서 접근 가능한 경로로 image_path를 DB에 저장한다. (예: /static/item_21.png)

3) (옵션) OpenAI Responses API를 이용해 이미지 대표 색상을 추출하고,
   - 미리 정해둔 COLOR_ENUM 목록 중 "정확히 하나"로만 저장되도록 강제한다.
   - GPT 호출은 시간이 걸리므로, 메시지 콜백(cb)에서 바로 호출하지 않고
     별도 스레드(gpt_worker)가 큐(queue)에서 작업을 가져가서 처리한다.
   - 결과가 나오면 DB의 color 컬럼만 UPDATE 한다.

즉,
  ROS2 DetectionResult 수신  ->  DB INSERT  ->  이미지 저장  ->  (옵션) GPT 색상 추출 후 UPDATE
"""
import os
import sqlite3
import threading
import queue
import base64
import re
import json
from typing import Tuple, Optional

import rclpy
from rclpy.node import Node

from cv_bridge import CvBridge
import cv2
import numpy as np

from my_robot_interfaces.msg import DetectionResult


# =========================================================
# ✅ 기본 설정(경로/토픽)
# =========================================================
DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"
UPLOAD_DIR = "/home/rokey/Desktop/amatta/static"
TOPIC_NAME = "/db_post"

os.makedirs(UPLOAD_DIR, exist_ok=True)

# ✅ SQLite는 동시에 여러 스레드가 접근하면 꼬일 수 있어서
#    DB 작업은 락(lock)을 걸어서 "한 번에 한 스레드만" 하도록 보호한다.
_db_lock = threading.Lock()
_bridge = CvBridge()

# ✅ USE_GPT_COLOR=1 / true면 GPT로 색상 추출
USE_GPT_COLOR = os.getenv("USE_GPT_COLOR", "0").strip().lower() in ("1", "true")

# ✅ OpenAI 클라이언트 준비
# - USE_GPT_COLOR가 켜져있고
# - openai 패키지가 설치되어 있고
# - OPENAI_API_KEY 환경변수가 설정되어 있으면
#   _client가 생성됨
_client = None
if USE_GPT_COLOR:
    try:
        from openai import OpenAI
        _client = OpenAI()
    except Exception:
        _client = None

# =========================================================
# ✅ GPT 작업을 "비동기"로 처리하기 위한 큐/스레드 설정
# =========================================================
# - cb()는 ROS 메시지가 들어올 때마다 호출되는데,
#   그 안에서 GPT 호출을 바로 하면 느려져서 메시지를 놓칠 수 있음.
# - 그래서 (item_id, 이미지)만 큐에 넣고 바로 빠져나오고,
#   gpt_worker 스레드가 큐에서 꺼내서 GPT 호출 + DB 업데이트를 한다.

_gpt_queue: "queue.Queue[Tuple[int, np.ndarray]]" = queue.Queue(maxsize=50)
_stop_event = threading.Event()

# =========================================================
# ✅ 색상 후보 목록(여기 있는 값만 DB에 저장되게 강제)
# =========================================================
COLOR_ENUM = [
    "검정", "흰색", "회색",
    "빨강", "주황", "노랑",
    "초록", "파랑", "보라",
    "분홍", "갈색", "베이지",
    "은색", "금색",
    "투명", "알수없음",
]

# ✅ (지원되는 경우) GPT 출력이 아래 JSON Schema를 "반드시" 따르게 강제
#    그리고 color 값은 enum 목록 중 하나만 가능
COLOR_SCHEMA = {
    "name": "color_result",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "color": {"type": "string", "enum": COLOR_ENUM}
        },
        "required": ["color"]
    }
}


"""
✅ 함수 역할
- DetectionResult 안의 pose에서 위치 좌표(x,y)를 꺼내준다.

왜 try/except를 쓰나?
- pose 구조가 예상과 다르거나 값이 없을 수도 있어서
    에러가 나면 (0.0, 0.0)으로 안전하게 처리하기 위함
"""
def get_xy_from_pose(pose_msg) -> Tuple[float, float]:
    try:
        return float(pose_msg.pose.position.x), float(pose_msg.pose.position.y)
    except Exception:
        return 0.0, 0.0


"""
✅ 함수 역할
- item 테이블에 새 레코드(행)를 1개 INSERT 하고
- 그 행의 id(자동 증가된 PK)를 리턴한다.
"""
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

"""
✅ 함수 역할
- item 테이블에서 특정 id의 image_path 컬럼을 업데이트한다.
- 웹에서 이미지 보여줄 때 /static/... 경로를 쓰도록 저장
"""
def update_item_image_path(item_id, image_path):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE item SET image_path=? WHERE id=?", (image_path, item_id))
        conn.commit()
        conn.close()


"""
✅ 함수 역할
- item 테이블에서 특정 id의 color 컬럼을 업데이트한다.
- GPT 결과(또는 실패 시 '알수없음')를 반영할 때 사용
"""
def update_item_color(item_id, color):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE item SET color=? WHERE id=?", (color, item_id))
        conn.commit()
        conn.close()


"""
✅ 함수 역할
- GPT가 이상한 텍스트를 주거나(예: '초록빛', 'green', '검은색' 등)
    형식이 약간 깨져도,
    최종적으로 DB에는 COLOR_ENUM 목록 중 하나만 저장되게 만든다.

처리 방식
1) 빈 값이면 "알수없음"
2) 공백/따옴표/줄바꿈 등 정리
3) 영문/변형(alias)을 한글 후보로 매핑
4) COLOR_ENUM에 없으면 "알수없음"
"""
def coerce_to_enum(raw: Optional[str]) -> str:
    if not raw:
        return "알수없음"

    s = str(raw).strip()
    s = re.split(r"[\n,\.]", s, maxsplit=1)[0]
    s = s.replace('"', "").replace("'", "").strip()

    # 흔한 영문/변형 대응 (원하면 더 추가)
    alias = {
        "green": "초록",
        "초록색": "초록",
        "초록빛": "초록",
        "연두": "초록",      # 원하면 "연두"를 enum에 넣고 별도로 유지해도 됨
        "lime": "초록",
        "blue": "파랑",
        "red": "빨강",
        "yellow": "노랑",
        "black": "검정",
        "white": "흰색",
        "gray": "회색",
        "grey": "회색",
        "brown": "갈색",
        "beige": "베이지",
        "pink": "분홍",
        "purple": "보라",
        "orange": "주황",
        "silver": "은색",
        "gold": "금색",
        "transparent": "투명",
    }

    if s in alias:
        s = alias[s]

    # enum에 없으면 "알수없음"
    if s not in COLOR_ENUM:
        return "알수없음"

    return s


"""
✅ 함수 역할
- OpenCV 이미지(np.ndarray)를 입력받아
- GPT(비전)로 대표 색상을 "1개" 골라서 반환한다.
- 반환 값은 COLOR_ENUM 중 하나로 강제된다.

중요 로직
1) 이미지를 PNG로 인코딩 -> base64 -> data URL로 만들어 GPT에 전달
2) 프롬프트로 "목록 중 하나만" 고르라고 강하게 지시
3) (가능하면) response_format=json_schema 로 enum 강제
4) 실패하면 fallback으로 다시 시도 후, 그래도 실패하면 "알수없음"
"""
def extract_color_with_gpt(cv_img: np.ndarray) -> str:
    if not USE_GPT_COLOR or _client is None:
        return "알수없음"

    ok, buf = cv2.imencode(".png", cv_img)
    if not ok:
        return "알수없음"

    b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
    data_url = f"data:image/png;base64,{b64}"

    # ✅ 프롬프트에서도 후보 목록만 허용한다고 강하게 고정
    prompt = (
        "이미지 속 물체의 대표 색상 1개를 선택해.\n"
        "아래 목록 중 '정확히 한 단어'만 고르고, 그 단어를 그대로 반환해.\n"
        "다른 단어(예: 초록색/초록빛/연두/green 등) 절대 금지.\n"
        f"허용 목록: {', '.join(COLOR_ENUM)}\n"
        '반환은 반드시 JSON 하나만: {"color":"허용목록중하나"}'
    )

    try:
        # ✅ 가능한 경우: enum이 걸린 JSON Schema로 형식/값을 강제
        # 모델/SDK 버전에 따라 tool/response_format 키가 다를 수 있어서
        # 아래는 "되면 강제" + "안 되면 파싱 fallback" 구조로 작성
        resp = _client.responses.create(
            model="gpt-4o-mini",
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url},
                ],
            }],
            # ✅ Structured Outputs (지원 시 강제)
            response_format={
                "type": "json_schema",
                "json_schema": COLOR_SCHEMA,
            },
        )

        out = (resp.output_text or "").strip()

        # 혹시 코드펜스가 섞이면 제거
        out = re.sub(r"^```(?:json)?\s*", "", out)
        out = re.sub(r"\s*```$", "", out).strip()

        obj = json.loads(out)
        return coerce_to_enum(obj.get("color"))

    except Exception:
        # ✅ Structured outputs가 실패하거나 모델이 깨진 경우를 대비해
        # 텍스트 파싱 fallback: 그래도 enum으로 강제 변환
        try:
            resp = _client.responses.create(
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
            out = re.sub(r"^```(?:json)?\s*", "", out)
            out = re.sub(r"\s*```$", "", out).strip()
            obj = json.loads(out)
            return coerce_to_enum(obj.get("color"))
        except Exception:
            return "알수없음"

"""
✅ 함수 역할
- _gpt_queue에서 (item_id, 이미지)를 하나씩 꺼내서
    GPT로 색상 추출 -> DB color 업데이트를 수행한다.
- ROS 콜백(cb)을 느리게 만들지 않기 위해 별도 스레드로 돌린다.
"""
def gpt_worker():
    while not _stop_event.is_set():
        try:
            item_id, cv_img = _gpt_queue.get(timeout=0.2)
        except queue.Empty:
            continue

        color = extract_color_with_gpt(cv_img) or "알수없음"
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

        if USE_GPT_COLOR and _client is not None:
            threading.Thread(target=gpt_worker, daemon=True).start()
            self.get_logger().info("GPT color extraction: ON")
        else:
            self.get_logger().info("GPT color extraction: OFF")
    """
    ✅ cb 역할(콜백 함수)

    - DetectionResult 메시지가 올 때마다 자동 실행된다.
    - 여기서는 "빠르게" DB 저장/이미지 저장만 하고,
        GPT는 큐에 넣어 비동기로 처리한다.

    (왜 빠르게 해야 하나?)
    - cb 안에서 오래 걸리면 다음 메시지를 놓칠 수 있음
    """
    def cb(self, msg: DetectionResult):
        try:
            category = (msg.class_name or "").strip() or "알수없음"
            robot_ns = (msg.ns or "").strip() or "unknown_robot"
            x, y = get_xy_from_pose(msg.pose)

            cv_img = _bridge.imgmsg_to_cv2(msg.image, desired_encoding="bgr8")

            item_id = insert_item_return_id(
                category,
                "추출중" if (USE_GPT_COLOR and _client is not None) else "알수없음",
                robot_ns,
                x,
                y,
            )

            filename = f"item_{item_id}.png"
            abs_path = os.path.join(UPLOAD_DIR, filename)
            cv2.imwrite(abs_path, cv_img)

            image_path = f"/static/{filename}"
            update_item_image_path(item_id, image_path)

            if USE_GPT_COLOR and _client is not None:
                try:
                    _gpt_queue.put_nowait((item_id, cv_img))
                except queue.Full:
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
