# load_db.py
import sqlite3
from typing import List, Dict, Any
from flask import Blueprint, render_template

# db 경로 지정
DB_PATH = "/home/coddyd/Desktop/workspace/Rokey/Team_amatta/sql/amatta.db"

# db 연결 및 data 추출 담당 내부 유틸리티 함수
def _fetch_all(table_name: str) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table_name};")
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

# 로봇 탐지, 보관 물품 전체 추출
def load_item():
    return _fetch_all("item")

# 사용자가 등록한 분실물 전체 추출
def load_item_lost():
    return _fetch_all("item_lost")

ad_load_db_bp = Blueprint("ad_load_db", __name__)

# 관리자용 아이템 목록 페이지 라우트
@ad_load_db_bp.route("/ad_load_db")
def ad_load_db():

    # 각 테이블에서 데이터 로드
    item = load_item()
    lost_item = load_item_lost()

    # 데이터가 있을 경우, 첫 번째 데이터의 키(id)를 추출하여 테이블 헤더용으로 사용
    # item.html에서 for문의 범위값으로 사용
    item_cols = list(item[0].keys()) if item else []
    lost_cols = list(lost_item[0].keys()) if lost_item else []

    # 렌더링을 위해 데이터를 템플릿(item.html)으로 전달
    return render_template(
        "item.html",
        item=item,
        item_cols=item_cols,
        lost_item=lost_item,
        lost_cols=lost_cols,
        db_path=DB_PATH
    )