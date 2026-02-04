from flask import render_template, request, jsonify, Blueprint
import sqlite3
import os

user_load_db_bp = Blueprint("user_load_db", __name__)
DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"

# 프로젝트 기준 static 절대 경로(환경에 맞게 1번만 맞추면 됨)
STATIC_ROOT = "/home/rokey/Desktop/amatta/static"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def to_public_url(image_path: str) -> str | None:
    """DB에 저장된 image_path를 브라우저가 접근 가능한 URL(/static/...)로 변환"""
    if not image_path:
        return None

    # 이미 URL 형태면 그대로
    if image_path.startswith("/static/"):
        return image_path

    # 로컬 절대경로가 static 아래면 /static/... 로 변환
    if image_path.startswith(STATIC_ROOT + "/"):
        rel = os.path.relpath(image_path, STATIC_ROOT)  # 예: uploads/wallet.jpg
        return "/static/" + rel.replace("\\", "/")

    # 그 외는 그대로 반환(원하면 None 처리 가능)
    return image_path

@user_load_db_bp.route("/")
def index():
    return render_template("user_item.html")

# ✅ guide_start.html에서 /user_load로 돌아가기 버튼을 쓰고 있어서 alias 추가
@user_load_db_bp.route("/user_load")
def user_load_alias():
    return render_template("user_item.html")

@user_load_db_bp.route("/filter", methods=["GET"])
# def filter_items():
#     category = request.args.get("category")
#     color = request.args.get("color")

#     conn = get_db()
#     query = "SELECT * FROM item WHERE state = '보관중'"
#     params = []

#     if category and category != "전체":
#         query += " AND category = ?"
#         params.append(category)

#     if color and color != "전체":
#         query += " AND color = ?"
#         params.append(color)

#     items = conn.execute(query, params).fetchall()
#     conn.close()

#     return jsonify([dict(ix) for ix in items])
def filter_items():
    category = request.args.get('category')
    color = request.args.get('color')

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    query = """
        SELECT
            *
        FROM item
        WHERE state = '보관중'
    """
    params = []

    if category != '전체':
        query += " AND category = ?"
        params.append(category)

    if color != '전체':
        query += " AND color = ?"
        params.append(color)

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    items = []
    for row in rows:
        d = dict(row)
        d["image_path"] = to_public_url(d.get("image_path"))
        items.append(d)

    return jsonify(items)
