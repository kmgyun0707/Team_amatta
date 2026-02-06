# guide_start.py
from flask import Blueprint, render_template, request, jsonify
import sqlite3
import json  # 형태가 있는 묶음을 한 번에, 안전하게, 확장 가능하게 보내기 위해 사용
import subprocess

guide_start_bp = Blueprint("guide_start", __name__)

DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"

LOST_AND_FOUND_POSE = {"frame": "map", "x": 1.20, "y": -0.80, "yaw": 0.0}
TOPIC_NAME = "/is_registered"       # 토픽 이름(추후 수정)
MSG_TYPE = "std_msgs/msg/String"    # 토픽 메시지 타입(추후 수정)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# 토픽 발행 함수
def publish_once(payload: dict):
    s = json.dumps(payload, ensure_ascii=False) # dict 문자열을 JSON 문자열로 바꿈

    # JSON 안전 escape
    escaped = s.replace('\\', '\\\\').replace('"', '\\"')
    msg = f'{{data: "{escaped}"}}'

    cmd = ["ros2", "topic", "pub", "-1", TOPIC_NAME, MSG_TYPE, msg] # 토픽을 한 번 발행하고 종료 
    subprocess.run(cmd, check=True, timeout=8) 

@guide_start_bp.route("/guide_start", methods=["GET"])
def guide_start_page():
    item_id = request.args.get("item_id", type=int)
    if item_id is None:
        return "item_id가 필요합니다", 400

    # 페이지는 무조건 렌더링 (토픽 발행은 JS에서 따로 호출)
    return render_template("guide_start.html", item_id=item_id)

@guide_start_bp.route("/api/publish_guidance", methods=["POST"])
def api_publish_guidance():
    try:
        data = request.get_json(force=True) or {}
        item_id = int(data.get("item_id"))

        conn = get_db()
        row = conn.execute("SELECT * FROM item WHERE id = ?", (item_id,)).fetchone()
        conn.close()

        if row is None:
            return jsonify({"ok": False, "error": "해당 분실물을 찾을 수 없습니다"}), 404

        item = dict(row)

        # ros로 보낼 payload
        payload = {
            "type": "start_guidance",
            "item_id": item.get("id"),
            "item": {
                "category": item.get("category"),
                "color": item.get("color"),
                "found_location": {"x": item.get("location_x"), "y": item.get("location_y")}
            },
            "target": {"name": "lost_and_found", **LOST_AND_FOUND_POSE}
        }

        # 실제 토픽 발행
        publish_once(payload)
        return jsonify({"ok": True})

    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "ros2 publish timeout"}), 504
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500