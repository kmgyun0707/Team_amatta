from flask import Blueprint, render_template, request, redirect
import sqlite3
import subprocess
from datetime import datetime
import threading

lost_report_bp = Blueprint("lost_report", __name__)
DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"

TOPIC_NAME = "/is_registered"
MSG_TYPE = "airport_guide_interfaces/msg/DbInfo"  # ✅

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def publish_dbinfo_once(registered: bool, item_id: int, counter: int, visited_spots: list[int], gate_id: int):
    msg_yaml = (
        "{"
        f"registered: {'true' if registered else 'false'}, "
        f"item_id: {int(item_id)}, "
        f"counter: {int(counter)}, "
        f"visited_spots: {visited_spots}, "
        f"gate_id: {int(gate_id)}"
        "}"
    )
    cmd = ["ros2", "topic", "pub", TOPIC_NAME, MSG_TYPE, msg_yaml]
    subprocess.run(cmd, check=True, timeout=8)

def publish_dbinfo_async(**kwargs):
    def _worker():
        try:
            publish_dbinfo_once(**kwargs)
        except Exception as e:
            print("[lost_report] publish failed:", repr(e))

    threading.Thread(target=_worker, daemon=True).start()

@lost_report_bp.route("/lost_report", methods=["GET"])
def lost_report_page():
    conn = get_db()
    locs = conn.execute("SELECT loc_id, loc_name FROM location ORDER BY loc_id").fetchall()
    conn.close()
    return render_template("lost_report.html", locations=locs)

@lost_report_bp.route("/lost_report", methods=["POST"])
def lost_report_submit():
    name = (request.form.get("name") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    category = (request.form.get("category") or "").strip()
    color = (request.form.get("color") or "").strip()

    # ✅ 신고시간
    losttime = (request.form.get("losttime") or "").strip()
    if not losttime:
        losttime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ✅ gate는 location의 loc_id
    gate_id = request.form.get("gate_id", "0")
    gate_id = int(gate_id) if str(gate_id).isdigit() else 0

    # ✅ 방문 경로(체크박스 loc_id)
    loc_ids = request.form.getlist("loc_id")
    loc_ids = [int(x) for x in loc_ids if str(x).isdigit()]

    conn = get_db()

    # 1) item_lost 저장
    cur = conn.execute(
        """
        INSERT INTO item_lost (name, phone, category, color, losttime, state)
        VALUES (?, ?, ?, ?, ?, '탐색중')
        """,
        (name, phone, category, color, losttime),
    )
    lost_id = cur.lastrowid

    # 2) 방문 경로 매핑 저장
    for loc_id in loc_ids:
        conn.execute(
            "INSERT INTO lost_location_map (lost_id, loc_id) VALUES (?, ?)",
            (lost_id, loc_id),
        )

    conn.commit()
    conn.close()

    # 3) 로봇에 탐색 시작 알림
    publish_dbinfo_async(
        registered=False,
        item_id=lost_id,
        counter=2,
        visited_spots=loc_ids,
        gate_id=gate_id
    )

    return redirect(f"/search_start?lost_id={lost_id}")
