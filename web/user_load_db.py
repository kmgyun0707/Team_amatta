from flask import render_template, request, jsonify, Blueprint
import sqlite3

user_load_db_bp = Blueprint("user_load_db", __name__)
DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@user_load_db_bp.route("/")
def index():
    return render_template("user_item.html")

# ✅ guide_start.html에서 /user_load로 돌아가기 버튼을 쓰고 있어서 alias 추가
@user_load_db_bp.route("/user_load")
def user_load_alias():
    return render_template("user_item.html")

@user_load_db_bp.route("/filter", methods=["GET"])
def filter_items():
    category = request.args.get("category")
    color = request.args.get("color")

    conn = get_db()
    query = "SELECT * FROM item WHERE state = '보관중'"
    params = []

    if category and category != "전체":
        query += " AND category = ?"
        params.append(category)

    if color and color != "전체":
        query += " AND color = ?"
        params.append(color)

    items = conn.execute(query, params).fetchall()
    conn.close()

    return jsonify([dict(ix) for ix in items])
