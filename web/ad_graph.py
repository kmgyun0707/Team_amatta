# # web/ad_graph.py
# import sqlite3
# from datetime import datetime, timedelta
# from flask import Blueprint, render_template, request, jsonify

# ad_graph_bp = Blueprint("ad_graph", __name__)

# DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"

# def get_db():
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     return conn

# @ad_graph_bp.route("/ad_graph")
# def ad_graph_page():
#     # 기본 날짜: 오늘
#     today = datetime.now().strftime("%Y-%m-%d")
#     return render_template("ad_graph.html", default_date=today)

# @ad_graph_bp.route("/ad_graph/data")
# def ad_graph_data():
#     """
#     Query params:
#       - date=YYYY-MM-DD (필수에 가깝지만 기본 오늘)
#       - days=정수 (최근 N일 추이, 기본 14)
#       - table=item_lost or item (선택, 기본 item_lost)
#     """
#     date_str = request.args.get("date")
#     days = request.args.get("days", "14")
#     table = request.args.get("table", "item_lost")  # 기본: 분실 신고 테이블

#     # date 기본값
#     if not date_str:
#         date_str = datetime.now().strftime("%Y-%m-%d")

#     try:
#         days = max(1, min(int(days), 90))  # 1~90 제한
#     except Exception:
#         days = 14

#     # 테이블 안전 처리
#     # (화이트리스트)
#     if table not in ("item_lost", "item"):
#         table = "item_lost"

#     # time 컬럼이 item_lost / item 모두 있다고 가정 (너 DB 설계상 item은 default current_timestamp)
#     # item_lost.time이 NULL일 수 있어도 date(time)에서 NULL이면 제외됨 → 필요하면 COALESCE 처리 가능
#     conn = get_db()
#     cur = conn.cursor()

#     # 1) 선택 날짜의 카테고리별 분실(신고) 건수
#     # SQLite date()는 'YYYY-MM-DD HH:MM:SS'면 잘 먹음
#     cur.execute(
#         f"""
#         SELECT
#             COALESCE(category, '기타') AS category,
#             COUNT(*) AS cnt
#         FROM {table}
#         WHERE date(time) = date(?)
#         GROUP BY category
#         ORDER BY cnt DESC
#         """,
#         (date_str,),
#     )
#     rows = cur.fetchall()
#     categories = [r["category"] for r in rows]
#     cat_counts = [int(r["cnt"]) for r in rows]

#     # 2) 최근 N일 일별 총 건수 (추이)
#     start_date = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=days - 1)).strftime("%Y-%m-%d")

#     cur.execute(
#         f"""
#         SELECT
#             date(time) AS d,
#             COUNT(*) AS cnt
#         FROM {table}
#         WHERE date(time) BETWEEN date(?) AND date(?)
#         GROUP BY date(time)
#         ORDER BY d ASC
#         """,
#         (start_date, date_str),
#     )
#     day_rows = cur.fetchall()
#     day_map = {r["d"]: int(r["cnt"]) for r in day_rows}

#     labels_days = []
#     counts_days = []
#     dt0 = datetime.strptime(start_date, "%Y-%m-%d")
#     dt1 = datetime.strptime(date_str, "%Y-%m-%d")
#     cur_dt = dt0
#     while cur_dt <= dt1:
#         d = cur_dt.strftime("%Y-%m-%d")
#         labels_days.append(d)
#         counts_days.append(day_map.get(d, 0))
#         cur_dt += timedelta(days=1)

#     conn.close()

#     return jsonify({
#         "selected_date": date_str,
#         "table": table,
#         "by_category": {
#             "labels": categories,
#             "counts": cat_counts
#         },
#         "trend_daily": {
#             "labels": labels_days,
#             "counts": counts_days
#         }
#     })


# web/ad_graph.py
import os
import sqlite3
import time
from datetime import datetime, timedelta
from typing import List, Dict

import yaml
from flask import Blueprint, render_template, request, jsonify, send_file, abort

from web.ros_monitor import MonitorStore, RosMonitorRunner

ad_graph_bp = Blueprint("ad_graph", __name__)

DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"
MAP_YAML_PATH = "/home/rokey/Desktop/maps/map.yaml"   # 너가 쓰는 경로로 맞춰
MAP_PNG_CACHE = "/home/rokey/Desktop/amatta/static/map_cache.png"  # pgm->png 변환 캐시

# ---- 전역(프로세스 메모리) ----
store = MonitorStore(max_logs=20)
runner = RosMonitorRunner(store)

# 방문자(메모리) 관리
visit_logs: List[dict] = []
visit_blocklist = set()
MAX_VISITS = 200


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@ad_graph_bp.before_app_request
def _track_visitors():
    # ad_graph 관련만 추적하고 싶으면 아래 if로 제한해도 됨
    path = request.path or ""
    if not path.startswith("/ad_graph"):
        return

    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    if ip in visit_blocklist:
        abort(403)

    ua = request.headers.get("User-Agent", "")
    now = time.time()

    visit_logs.append({
        "stamp": now,
        "ip": ip,
        "path": path,
        "ua": ua[:120],
    })
    if len(visit_logs) > MAX_VISITS:
        del visit_logs[: len(visit_logs) - MAX_VISITS]


@ad_graph_bp.route("/ad_graph")
def ad_graph_page():
    # ROS 모니터 시작(한 번만)
    runner.start()

    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("ad_graph.html", default_from=today, default_to=today)


# ---------------------------
# 1) 실시간 모니터링 API (2초 폴링)
# ---------------------------
@ad_graph_bp.route("/ad_graph/api/monitor")
def api_monitor():
    snap = store.snapshot()
    return jsonify(snap)


# ---------------------------
# 2) 오늘 찾은 item 테이블 API
#    item.time = datetime default current_timestamp
#    image는 image_path(/static/xxx.png)를 그대로 사용
# ---------------------------
@ad_graph_bp.route("/ad_graph/api/today_items")
def api_today_items():
    date_str = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, category, color, robot_name, time, location_x, location_y, image_path, state
        FROM item
        WHERE date(time) = date(?)
        ORDER BY id DESC
        LIMIT 100
        """,
        (date_str,),
    )
    rows = cur.fetchall()
    conn.close()

    items = []
    for r in rows:
        items.append({
            "id": r["id"],
            "category": r["category"],
            "color": r["color"],
            "robot_name": r["robot_name"],
            "time": r["time"],
            "x": r["location_x"],
            "y": r["location_y"],
            "image_url": r["image_path"],  # /static/xxx
            "state": r["state"],
        })
    return jsonify({"date": date_str, "items": items})


# ---------------------------
# 3) 통계 API (기간 from~to)
#    - 일자별 찾은 분실물(= item insert count)
#    - 회수율(= 회수 / 전체 신고) : item_lost 기준
# ---------------------------
@ad_graph_bp.route("/ad_graph/api/stats")
def api_stats():
    date_from = request.args.get("from") or datetime.now().strftime("%Y-%m-%d")
    date_to = request.args.get("to") or datetime.now().strftime("%Y-%m-%d")

    # 날짜 정리
    try:
        dt0 = datetime.strptime(date_from, "%Y-%m-%d")
        dt1 = datetime.strptime(date_to, "%Y-%m-%d")
    except Exception:
        dt0 = dt1 = datetime.now()

    if dt1 < dt0:
        dt0, dt1 = dt1, dt0

    # 너무 길면 제한(예: 180일)
    if (dt1 - dt0).days > 180:
        dt1 = dt0 + timedelta(days=180)

    f = dt0.strftime("%Y-%m-%d")
    t = dt1.strftime("%Y-%m-%d")

    conn = get_db()
    cur = conn.cursor()

    # (A) 일자별 "찾은 분실물" = item 추가 건수
    cur.execute(
        """
        SELECT date(time) as d, COUNT(*) as cnt
        FROM item
        WHERE date(time) BETWEEN date(?) AND date(?)
        GROUP BY date(time)
        ORDER BY d ASC
        """,
        (f, t),
    )
    rows = cur.fetchall()
    day_map = {r["d"]: int(r["cnt"]) for r in rows}

    labels = []
    counts = []
    cur_dt = dt0
    while cur_dt <= dt1:
        d = cur_dt.strftime("%Y-%m-%d")
        labels.append(d)
        counts.append(day_map.get(d, 0))
        cur_dt += timedelta(days=1)

    # (B) 회수율 도넛: 회수 / 전체 신고 (item_lost)
    # 전체 신고 = 기간 내 item_lost 전체
    cur.execute(
        """
        SELECT COUNT(*) as total
        FROM item_lost
        WHERE date(time) BETWEEN date(?) AND date(?)
        """,
        (f, t),
    )
    total_report = int(cur.fetchone()["total"] or 0)

    cur.execute(
        """
        SELECT COUNT(*) as recovered
        FROM item_lost
        WHERE date(time) BETWEEN date(?) AND date(?)
          AND state = '회수'
        """,
        (f, t),
    )
    recovered = int(cur.fetchone()["recovered"] or 0)

    conn.close()

    not_recovered = max(0, total_report - recovered)
    rate = (recovered / total_report * 100.0) if total_report > 0 else 0.0

    return jsonify({
        "from": f,
        "to": t,
        "found_daily": {"labels": labels, "counts": counts},
        "recovery": {
            "total_report": total_report,
            "recovered": recovered,
            "not_recovered": not_recovered,
            "rate": rate
        }
    })


# ---------------------------
# 4) 지도(맵) 관련 API
#    - map.yaml 읽고 resolution/origin 가져오기
#    - pgm이면 png로 변환해서 제공
# ---------------------------
def _ensure_map_png() -> str:
    # MAP_YAML_PATH의 image 파일이 pgm일 가능성이 높음 -> png로 캐시
    with open(MAP_YAML_PATH, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f)

    img_path = meta.get("image")
    if not img_path:
        raise RuntimeError("map.yaml에 image가 없습니다.")

    # 상대경로면 yaml 기준으로 해석
    if not os.path.isabs(img_path):
        img_path = os.path.join(os.path.dirname(MAP_YAML_PATH), img_path)

    # png/jpg면 그대로 제공
    ext = os.path.splitext(img_path)[1].lower()
    if ext in (".png", ".jpg", ".jpeg"):
        return img_path

    # pgm면 png 변환(한 번만)
    if os.path.exists(MAP_PNG_CACHE) and os.path.getmtime(MAP_PNG_CACHE) >= os.path.getmtime(img_path):
        return MAP_PNG_CACHE

    # Pillow로 pgm 읽어서 png 저장
    from PIL import Image
    im = Image.open(img_path)
    im.save(MAP_PNG_CACHE)
    return MAP_PNG_CACHE


@ad_graph_bp.route("/ad_graph/api/map_meta")
def api_map_meta():
    with open(MAP_YAML_PATH, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f)

    resolution = float(meta.get("resolution", 0.05))
    origin = meta.get("origin", [0, 0, 0])
    origin_x = float(origin[0])
    origin_y = float(origin[1])

    # 맵 이미지 라우트
    return jsonify({
        "resolution": resolution,
        "origin": {"x": origin_x, "y": origin_y},
        "image_url": "/ad_graph/map_image"
    })


@ad_graph_bp.route("/ad_graph/map_image")
def map_image():
    try:
        path = _ensure_map_png()
        return send_file(path)
    except Exception as e:
        return abort(500, str(e))


# ---------------------------
# 5) 방문자 관리 API (메모리)
# ---------------------------
@ad_graph_bp.route("/ad_graph/api/visitors")
def api_visitors():
    # 최근순
    data = list(reversed(visit_logs[-MAX_VISITS:]))
    return jsonify({"visitors": data, "blocked": sorted(list(visit_blocklist))})


@ad_graph_bp.route("/ad_graph/api/visitors/block", methods=["POST"])
def api_visitors_block():
    ip = (request.json or {}).get("ip", "")
    if ip:
        visit_blocklist.add(ip)
    return jsonify({"ok": True, "blocked": sorted(list(visit_blocklist))})


@ad_graph_bp.route("/ad_graph/api/visitors/unblock", methods=["POST"])
def api_visitors_unblock():
    ip = (request.json or {}).get("ip", "")
    if ip in visit_blocklist:
        visit_blocklist.remove(ip)
    return jsonify({"ok": True, "blocked": sorted(list(visit_blocklist))})
