# [lost_report.py 전체 기능]
# 사용자로부터 "분실물 신고" 정보를 웹(Flask) 폼으로 입력받아 SQLite DB에 저장하고,
# 저장된 분실물 ID/방문장소/게이트 정보를 ROS2 토픽(/is_registered, DbInfo 메시지)으로 비동기 발행한 뒤,
# 탐색 시작 화면(/search_start)으로 리다이렉트하는 Flask Blueprint 모듈

from flask import Blueprint, render_template, request, redirect
import sqlite3
import subprocess
from datetime import datetime
import threading


# Flask에서 페이지 묶음을 만들기 위한 Blueprint
# (lost_report 관련 페이지들을 하나의 묶음으로 관리)
lost_report_bp = Blueprint("lost_report", __name__)

# 분실물 정보를 저장할 SQLite 데이터베이스 파일 경로
DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"

# 로봇과 통신하기 위한 ROS2 토픽 이름과 메시지 타입
TOPIC_NAME = "/is_registered"
MSG_TYPE = "airport_guide_interfaces/msg/DbInfo"  # ✅

# 데이터베이스(DB)에 연결하는 함수
# 이 함수를 호출하면 DB와 연결된 통로(conn)를 돌려준다.
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# 로봇에게 보낼 메시지를 만든다.
def publish_dbinfo(registered: bool, item_id: int, counter: int, visited_spots: list[int], gate_id: int):
    msg_yaml = (
        "{"
        f"registered: {'true' if registered else 'false'}, "    # registered     : 이미 DB에 있는 물건인지 여부 (true / false)
        f"item_id: {int(item_id)}, "                            # item_id        : 분실물의 DB 번호 (로봇이 DB에서 찾기 위한 번호)
        f"counter: {int(counter)}, "                            # counter        : 안내해야하는 카운터의 위치
        f"visited_spots: {visited_spots}, "                     # visited_spots  : 사용자가 방문했다고 선택한 장소들
        f"gate_id: {int(gate_id)}"                              # gate_id        : 사용자가 대기할 게이트 번호
        "}"
    )

    # 터미널에서 입력할 명령어를 파이썬에서 실행해주는 것
    cmd = ["ros2", "topic", "pub", TOPIC_NAME, MSG_TYPE, msg_yaml]
    subprocess.run(cmd, check=True, timeout=8)

# 로봇에게 메시지를 "따로" 보내기 위한 함수
# 메시지를 보내느라 웹 화면이 멈추지 않도록 백그라운드에서 실행한다.
def publish_dbinfo_async(**kwargs):
    def _worker():
        try:
            publish_dbinfo(**kwargs)
        except Exception as e:
            print("[lost_report] publish failed:", repr(e))

    # 새로운 쓰레드를 만들어서 실행
    threading.Thread(target=_worker, daemon=True).start()

# /lost_report 주소를 GET 방식으로 요청하면 아래 함수 실행 (GET의 역할 : 화면 보여달라고 요청)
@lost_report_bp.route("/lost_report", methods=["GET"])

# 분실물 신고 화면을 처음 열 때 실행되는 함수(주소창에 /lost_report 입력했을 때)
def lost_report_page():
    conn = get_db()

    # location 테이블에서 loc_name과 loc_id를 가져온다.
    locs = conn.execute("SELECT loc_id, loc_name FROM location ORDER BY loc_id").fetchall()
    conn.close()

    # HTML 화면에 장소 목록을 전달
    return render_template("lost_report.html", locations=locs)

# /lost_report 주소로 POST 방식으로 요청이 오면 아래 함수 실행 (POST의 역할 : 데이터를 서버에 전달)
@lost_report_bp.route("/lost_report", methods=["POST"])

# 신고하기 버튼 클릭시 실행되는 함수
def lost_report_submit():

    # 사용자 입력값 가져오기
    name = (request.form.get("name") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    category = (request.form.get("category") or "").strip()
    category_etc = (request.form.get("category_etc") or "").strip()
    if category == "기타" and category_etc:
        category = category_etc
        
    color = (request.form.get("color") or "").strip()
    color_etc = (request.form.get("color_etc") or "").strip()
    if color == "기타" and color_etc:
        color = color_etc

    # ✅ 신고시간(입력값 없을 시 현재 시간으로 자동 저장)
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

    # 분실물 정보를 item_lost 테이블에 저장
    cur = conn.execute(
        """
        INSERT INTO item_lost (name, phone, category, color, losttime, state)
        VALUES (?, ?, ?, ?, ?, '탐색중')
        """,
        (name, phone, category, color, losttime),
    )

    # 방금 저장된 분실물의 고유 번호
    lost_id = cur.lastrowid

    # 방문 경로 저장
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
