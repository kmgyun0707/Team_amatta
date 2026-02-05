# 이 파일은 "사용자가 분실물 DB를 조회하는 화면"을 담당하는 프로그램이다.
# 사용자가 웹 페이지에서
# - 분실물 목록을 보고
# - 카테고리/색상으로 필터링하면
# 그 조건에 맞는 분실물 정보를 DB에서 꺼내서
# 웹 화면에 JSON 형태로 전달해준다.

from flask import render_template, request, jsonify, Blueprint
import sqlite3
import os

# user_load_db 관련 페이지들을 묶어서 관리하기 위한 Blueprint
user_load_db_bp = Blueprint("user_load_db", __name__)


# SQLite 데이터베이스 파일 경로
DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"

# 프로젝트 기준 static 절대 경로(이미지 파일을 웹에서 보여주기 위해 필요)
STATIC_ROOT = "/home/rokey/Desktop/amatta/static"

CATEGORY_MAP = {
    "이어폰": ["이어폰", "에어팟", "무선이어폰", "블루투스 이어폰", "AirPods", "airpods", "earbuds"],
    "지갑": ["지갑", "wallet", "카드지갑", "명함지갑"],
    "스마트폰": ["스마트폰", "휴대폰", "핸드폰", "phone", "iphone", "galaxy"],
    "가방": ["가방", "백팩", "백", "배낭", "bag", "backpack", "핸드백", "쇼핑백"],
    "여권": ["여권", "여권케이스"]
}
COLOR_MAP = {
    "빨강색": ["빨강색", "빨강", "레드", "red"],
    "주황색": ["주황색", "주황", "오렌지", "orange"],
    "노란색": ["노란색", "노랑색", "노랑", "옐로우", "yellow"],
    "초록색": ["초록색", "카키", "초록","녹색", "그린", "green"],
    "파랑색": ["파랑색", "파란색", "파랑", "블루", "blue"],
    "남색": ["남색", "곤색", "군청색", "네이비", "navy"],
    "갈색": ["갈색", "브라운", "brown"],
    "검정색": ["검정색", "검정", "블랙", "black"],
    "흰색": ["흰색", "하양색", "하양", "백색", "화이트", "white"],
    "투명": ["투명", "무색", "클리어", "clear"]
}

# 데이터베이스(DB)에 연결하는 함수
# 이 함수를 호출하면 DB와 연결된 통로(conn)를 돌려준다.
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# DB에 저장된 image_path를 브라우저가 접근 가능한 URL로 변환
def to_public_url(image_path: str) -> str | None:
    if not image_path:
        return None

    # 이미 URL 형태면 그대로
    if image_path.startswith("/static/"):
        return image_path

    # 로컬 절대경로가 static 아래면 /static/... 로 변환
    if image_path.startswith(STATIC_ROOT + "/"):
        rel = os.path.relpath(image_path, STATIC_ROOT)  # 예: uploads/wallet.jpg
        return "/static/" + rel.replace("\\", "/")

    # 그 외는 그대로 반환
    return image_path

@user_load_db_bp.route("/")
# 사용자가 사이트에 처음 들어오면 분실물 조회 화면(user_item.html)을 보여준다.
def index():
    return render_template("user_item.html")

# guide_start.html에서 /user_load로 돌아가기 버튼을 쓰고 있어서 alias 추가
@user_load_db_bp.route("/user_load")
def user_load_alias():
    return render_template("user_item.html")

# /filter 주소를 GET 방식으로 요청하면 아래 함수 실행 (GET의 역할 : 화면 보여달라고 요청)
@user_load_db_bp.route("/filter", methods=["GET"])

# 사용자가 선택한 필터 값 받는 함수
def filter_items():
    category = request.args.get('category')
    color = request.args.get('color')

    category_etc = (request.args.get("category_etc") or "").strip()
    color_etc = (request.args.get("color_etc") or "").strip()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 현재 상태가 '보관중'인 분실물만 조회
    query = """
        SELECT
            *
        FROM item
        WHERE state = '보관중'
    """
    params = []

    # 카테고리 필터가 "전체"가 아니면 조건 추가
    if category == "기타":
        # 기타인데 입력이 비어있으면 => 전체(필터 적용 X)
        if category_etc:
            query += " AND category LIKE ?"
            params.append(f"%{category_etc}%")
    elif category != "전체":
        keys = CATEGORY_MAP.get(category, [category])
        query += " AND (" + " OR ".join(["category LIKE ?"] * len(keys)) + ")"
        params.extend([f"%{k}%" for k in keys])

    # 색상 필터가 "전체"가 아니면 조건 추가
    if color == "기타":
        if color_etc:
            query += " AND color LIKE ?"
            params.append(f"%{color_etc}%")
    elif color != "전체":
        keys = COLOR_MAP.get(color, [color])
        query += " AND (" + " OR ".join(["color LIKE ?"] * len(keys)) + ")"
        params.extend([f"%{k}%" for k in keys])

    # 완성된 쿼리 실행
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    
    # DB 결과를 JSON으로 바꾸기 위한 처리
    items = []
    for row in rows:
        d = dict(row)
        d["image_path"] = to_public_url(d.get("image_path"))
        items.append(d)

    # JSON 형태로 프론트엔드롤 전달
    return jsonify(items)
