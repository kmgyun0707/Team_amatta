# ✅ 이 파일은 "분실물이 이미 DB에 존재할 때"
# 사용자에게 안내 화면을 보여주고,
# 동시에 로봇에게 "안내 시작" 신호를 보내는 역할을 한다.
# 즉,
# 분실물이 이미 보관 중인 경우
# 로봇이 사용자를 분실물 보관 장소로 안내하도록 만드는 코드다.

from flask import Blueprint, request, render_template
import subprocess
import threading

# Flask에서 페이지 묶음을 만들기 위한 Blueprint
# (guide_start 관련 페이지들을 하나의 묶음으로 관리)
guide_start_bp = Blueprint("guide_start", __name__)

# 로봇과 통신할 ROS2 토픽 이름 & 타입
TOPIC_NAME = "/is_registered"
MSG_TYPE = "airport_guide_interfaces/msg/DbInfo"

# 로봇에게 보낼 메시지 생성
def publish_dbinfo(registered: bool, item_id: int, counter: int, visited_spots: list[int], gate_id: int):
    msg_yaml = (
        "{"
        f"registered: {'true' if registered else 'false'}, "    # registered     : DB에 이미 있는 분실물인지 여부
        f"item_id: {int(item_id)}, "                            # item_id        : 분실물의 DB ID
        f"counter: {int(counter)}, "                            # counter        : 분실물 보관함의 위치값
        f"visited_spots: {visited_spots}, "                     # visited_spots  : 방문 장소 리스트 (안내에서는 비워둠)
        f"gate_id: {int(gate_id)}"                              # gate_id        : 안내 목적지(보관 장소 ID 등)
        "}"
    )

    # 터미널에 직접 치는 명령어를 파이썬 코드에서 실행
    cmd = ["ros2", "topic", "pub", TOPIC_NAME, MSG_TYPE, msg_yaml]
    subprocess.run(cmd, check=True, timeout=8)

# 로봇에게 신호를 보낼 때 웹페이지 로빙이 멈추지 않도록 토픽 발행에 대해 백그라운드에서 실행하는 함수
def publish_dbinfo_async(**kwargs):
    def _worker():
        try:
            publish_dbinfo(**kwargs)
        except Exception as e:
            # 문제가 생겨도 웹은 정상 동작
            print("[guide_start] publish failed:", repr(e))

    # 새로운 스레드를 만들어 실행
    t = threading.Thread(target=_worker, daemon=True)
    t.start()

# /guide_start 주소를 GET 방식으로 요청하면 아래 함수 실행 (GET의 역할 : 화면 보여달라고 요청)
@guide_start_bp.route("/guide_start", methods=["GET"])

def guide_start_page():
    # item_id : 분실물 DB ID
    item_id = request.args.get("item_id", type=int)
    # counter : 분실물 보관소의 위치값 (기본값 2)
    counter = request.args.get("counter", default=2, type=int)
    if not item_id:
        return "item_id가 필요합니다.", 400

    # 보관중 분실물 안내 시작 publish
    publish_dbinfo_async(
        registered=True,
        item_id=item_id,
        counter=2,
        visited_spots=[],
        gate_id=8
    )

    return render_template("guide_start.html", item_id=item_id, counter=counter)
