# ad_detect.py

from flask import Blueprint, render_template

ad_detect_bp = Blueprint("ad_detect", __name__)

@ad_detect_bp.route("/ad_detect")
def ad_detect_page():
    return render_template("ad_detect.html")
# 2/4 개발 예정