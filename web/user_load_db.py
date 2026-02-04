from flask import render_template, request, jsonify, Blueprint, redirect, url_for, session, flash
import sqlite3

# 블루프린트 생성(이 파일 안의 라우트들을 user_load_db에 등록 해두고 main.py 에서 사용)
user_load_db_bp = Blueprint("user_load_db", __name__)

# DB경로
DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"

# DB연결 함수
def get_db():
    conn = sqlite3.connect(DB_PATH)   # DB파일 연결
    conn.row_factory = sqlite3.Row    # 조회결과를 딕셔너리 형태로 설정
    return conn

@user_load_db_bp.route("/")         #url로 들어오면 아래 함수가 실행됨
def index():
    return render_template('user_item.html')              # user_item.html 렌더링

@user_load_db_bp.route("/filter", methods=["GET"])
def filter_items():
    category = request.args.get('category')               # DB에 있는 데이터 중 category, color에 해당하는 값 읽음
    color = request.args.get('color')                     
    
    conn = get_db()                                        # DB연결 함수 변수에 저장
    query = "SELECT * FROM item WHERE state = '보관중'"     # item 테이블에서 state가 '보관중'인 데이터만 조회
    params = []
    
    if category and category != '전체':                    # category값이 존재하고 '전체'를 선택하지 않았을 때
        query += " AND category = ?"                      # SQL문에 AND category = ? 조건을 붙임
        params.append(category)                           # ? 자리에 들어갈 실제 값을 리스트에 추가
  
    # category와 동일한 방식
    if color and color != '전체':
        query += " AND color = ?"
        params.append(color)
        
    items = conn.execute(query, params).fetchall()        # query 안의 ?들을 params 값으로 안전하게 치환해서 실행
    conn.close()                                          # DB 연결 닫기
    
    # 결과를 리스트 형태로 변환하여 전송
    return jsonify([dict(ix) for ix in items])