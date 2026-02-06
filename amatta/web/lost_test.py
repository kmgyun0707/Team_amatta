import subprocess

TOPIC_NAME = "/is_registered"
MSG_TYPE = "airport_guide_interfaces/msg/DBInfo"

def publish_dbinfo_once(registered, item_id, counter, visited_spots, gate_id):
    msg_yaml = (
        "{"
        f"registered: {'true' if registered else 'false'}, "
        f"item_id: {int(item_id)}, "
        f"counter: {int(counter)}, "
        f"visited_spots: {visited_spots}, "
        f"gate_id: {int(gate_id)}"
        "}"
    )
    cmd = ["ros2", "topic", "pub", "-1", TOPIC_NAME, MSG_TYPE, msg_yaml]

    res = subprocess.run(cmd, text=True, capture_output=True, timeout=8)  # ✅ check=False
    if res.returncode != 0:
        print("\n❌ ros2 topic pub 실패")
        print("CMD:", " ".join(cmd))
        print("STDOUT:", res.stdout.strip())
        print("STDERR:", res.stderr.strip())
        return False, res.stderr.strip()

    return True, res.stdout.strip()
