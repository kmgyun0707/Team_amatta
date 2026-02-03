from flask import Blueprint, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

lost_report_bp = Blueprint("lost_report", __name__)

DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ✅ 신고 입력 화면
@lost_report_bp.route("/lost_report", methods=["GET"])
def lost_report_page():
    return render_template("lost_report.html")


# ✅ 신고 저장 처리
@lost_report_bp.route("/lost_report", methods=["POST"])
def lost_report_submit():
    name = request.form.get("name")
    phone = request.form.get("phone")
    category = request.form.get("category")
    color = request.form.get("color")
    time_value = request.form.get("time")
    locations = request.form.getlist("location")

    if not time_value:
        time_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    location_text = ", ".join(locations)

    conn = get_db()
    conn.execute(
        """
        INSERT INTO item_lost
        (name, phone, category, color, time, location, state)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (name, phone, category, color, time_value, location_text, "접수")
    )
    conn.commit()
    conn.close()

    # 신고 후 다시 목록 화면
    return redirect("/user_load")
