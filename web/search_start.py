# from flask import Blueprint, request, render_template

# search_start_bp = Blueprint("search_start", __name__)

# @search_start_bp.route("/search_start", methods=["GET"])
# def search_start_page():
#     lost_id = request.args.get("lost_id", type=int)
#     return render_template("search_start.html", lost_id=lost_id)
from flask import Blueprint, request, render_template, jsonify
import sqlite3

search_start_bp = Blueprint("search_start", __name__)

DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@search_start_bp.route("/search_start", methods=["GET"])
def search_start_page():
    lost_id = request.args.get("lost_id", type=int)
    return render_template("search_start.html", lost_id=lost_id)

# ✅ 1) 프론트가 폴링으로 상태를 물어보는 API
@search_start_bp.route("/search_status", methods=["GET"])
def search_status():
    lost_id = request.args.get("lost_id", type=int)
    if not lost_id:
        return jsonify({"ok": False, "error": "missing lost_id"}), 400

    conn = get_db()
    row = conn.execute("SELECT state FROM item_lost WHERE id = ?", (lost_id,)).fetchone()
    conn.close()

    if not row:
        return jsonify({"ok": False, "error": "not found"}), 404

    state = row["state"]
    # state: "탐색중" / "분실" / "회수"
    return jsonify({"ok": True, "state": state})

# ✅ 2) 결과 페이지들(새 파일로 렌더)
@search_start_bp.route("/search_success", methods=["GET"])
def search_success():
    lost_id = request.args.get("lost_id", type=int)
    return render_template("search_success.html", lost_id=lost_id)

@search_start_bp.route("/search_fail", methods=["GET"])
def search_fail():
    lost_id = request.args.get("lost_id", type=int)
    return render_template("search_fail.html", lost_id=lost_id)
