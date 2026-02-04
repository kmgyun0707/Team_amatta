from flask import render_template, request, jsonify, Blueprint, redirect, url_for, session, flash
import sqlite3

user_load_db_bp = Blueprint("user_load_db", __name__)

DB_PATH = "/home/coddyd/Desktop/workspace/Rokey/Team_amatta/sql/amatta.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@user_load_db_bp.route("/")
def index():
    return render_template('user_item.html')

@user_load_db_bp.route("/filter", methods=["GET"])
def filter_items():
    category = request.args.get('category')
    color = request.args.get('color')
    
    conn = get_db_connection()
    query = "SELECT * FROM item WHERE state = '보관중'"
    params = []
    
    if category and category != '전체':
        query += " AND category = ?"
        params.append(category)
    if color and color != '전체':
        query += " AND color = ?"
        params.append(color)
        
    items = conn.execute(query, params).fetchall()
    conn.close()
    
    # 결과를 리스트 형태로 변환하여 전송
    return jsonify([dict(ix) for ix in items])
