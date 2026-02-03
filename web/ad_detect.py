# ad_detect.py
from flask import Flask, render_template, request, redirect, url_for, session, flash

from flask import Blueprint, render_template

ad_detect_bp = Blueprint(
    "ad_detect",
    __name__,
    template_folder="/home/rokey/Desktop/amatta/template"
)

@ad_detect_bp.route("/ad_detect")
def ad_detect_page():
    return render_template("ad_detect.html")
