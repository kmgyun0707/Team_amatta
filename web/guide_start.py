from flask import Blueprint, request, render_template
import subprocess
import threading
import os

guide_start_bp = Blueprint("guide_start", __name__)

TOPIC_NAME = "/is_registered"
MSG_TYPE = "airport_guide_interfaces/msg/DbInfo"  # ✅ 대소문자 포함 네가 준 그대로

def publish_dbinfo_once(registered: bool, item_id: int, counter: int, visited_spots: list[int], gate_id: int):
    msg_yaml = (
        "{"
        f"registered: {'true' if registered else 'false'}, "
        f"item_id: {int(item_id)}, "
        f"counter: {int(counter)}, "
        f"visited_spots: {visited_spots}, "
        f"gate_id: {int(gate_id)}"
        "}"
    )
    cmd = ["ros2", "topic", "pub", TOPIC_NAME, MSG_TYPE, msg_yaml]
    subprocess.run(cmd, check=True, timeout=8)

def publish_dbinfo_async(**kwargs):
    """페이지 응답을 막지 않도록 publish를 별도 스레드로 실행"""
    def _worker():
        try:
            publish_dbinfo_once(**kwargs)
        except Exception as e:
            print("[guide_start] publish failed:", repr(e))

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


@guide_start_bp.route("/guide_start", methods=["GET"])
def guide_start_page():
    item_id = request.args.get("item_id", type=int)
    counter = request.args.get("counter", default=2, type=int)
    if not item_id:
        return "item_id가 필요합니다.", 400

    # ✅ 보관중 분실물 안내 시작 publish
    publish_dbinfo_async(
        registered=True,
        item_id=item_id,
        counter=2,
        visited_spots=[],
        gate_id=8
    )

    return render_template("guide_start.html", item_id=item_id, counter=counter)
