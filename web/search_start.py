from flask import Blueprint, request, render_template

search_start_bp = Blueprint("search_start", __name__)

@search_start_bp.route("/search_start", methods=["GET"])
def search_start_page():
    lost_id = request.args.get("lost_id", type=int)
    return render_template("search_start.html", lost_id=lost_id)
