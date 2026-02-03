# load_db.py
import sqlite3
from typing import List, Dict, Any
from flask import Blueprint, render_template

DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"


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

def load_item():
    return _fetch_all("item")

def load_item_lost():
    return _fetch_all("item_lost")

ad_load_db_bp = Blueprint("ad_load_db", __name__)

@ad_load_db_bp.route("/ad_load_db")
def ad_load_db():
    item = load_item()
    lost_item = load_item_lost()

    item_cols = list(item[0].keys()) if item else []
    lost_cols = list(lost_item[0].keys()) if lost_item else []

    return render_template(
        "item.html",
        item=item,
        item_cols=item_cols,
        lost_item=lost_item,
        lost_cols=lost_cols,
        db_path=DB_PATH
    )