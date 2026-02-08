# search_start.py
# 탐색을 시작했을때 나타나는 페이지
# 분실물 발견 시 /search_success 페이지로 전환
# 분실물 발견 실패 시 /search_fail 페이지로 전환
from flask import Blueprint, request, render_template, jsonify
import sqlite3

# ✅ Blueprint 생성
# - Flask에서 기능 단위로 라우트를 모듈화하기 위한 객체
search_start_bp = Blueprint("search_start", __name__)

# ✅ SQLite DB 경로
DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"

# DB 연결 생성 함수
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

"""
탐색 진행(대기) 페이지 렌더
사용자 분실 신고/탐색 시작 버튼 클릭
/search_start?lost_id=123 로 이동
search_start.html 에서 JS가 lost_id를 가지고 /search_status 를 폴링하기 시작
"""
@search_start_bp.route("/search_start", methods=["GET"])
def search_start_page():
    lost_id = request.args.get("lost_id", type=int)
    return render_template("search_start.html", lost_id=lost_id)

"""
✅ 프론트엔드가 주기적으로 호출하는 상태 조회 API (폴링 API)
요청 예:
    - GET /search_status?lost_id=123

    응답 예:
    - 정상:
      {"ok": true, "state": "탐색중"}
      {"ok": true, "state": "회수"}
      {"ok": true, "state": "분실"}
"""
@search_start_bp.route("/search_status", methods=["GET"])
def search_status():
    lost_id = request.args.get("lost_id", type=int)
    if not lost_id:
        return jsonify({"ok": False, "error": "missing lost_id"}), 400

    conn = get_db()

    # ✅ item_lost에서 해당 id의 state만 조회
    # - 파라미터 바인딩(?, (lost_id,))을 써서 SQL injection 방지
    row = conn.execute("SELECT state FROM item_lost WHERE id = ?", (lost_id,)).fetchone()
    conn.close()

    if not row:
        return jsonify({"ok": False, "error": "not found"}), 404

    state = row["state"]
    # ✅ 상태 값은 프론트가 분기 처리에 사용
    # 예: state=="회수"면 /search_success로 이동
    #     state=="분실"이면 /search_fail로 이동
    return jsonify({"ok": True, "state": state})

# ✅ 탐색 성공(회수) 결과 페이지
@search_start_bp.route("/search_success", methods=["GET"])
def search_success():
    lost_id = request.args.get("lost_id", type=int)
    return render_template("search_success.html", lost_id=lost_id)

# ✅ 탐색 실패(분실) 결과 페이지
@search_start_bp.route("/search_fail", methods=["GET"])
def search_fail():
    lost_id = request.args.get("lost_id", type=int)
    return render_template("search_fail.html", lost_id=lost_id)
