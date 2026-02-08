#!/usr/bin/env python3
# 키보드 스페이스바 누르면 db 토픽 발행 
import sys
import threading
import rclpy
from rclpy.node import Node
from airport_guide_interfaces.msg import DbInfo

TOPIC_NAME = "/is_registered"


class KeyDbInfoPub(Node):
    def __init__(self):
        super().__init__("key_dbinfo_pub")
        self.pub = self.create_publisher(DbInfo, TOPIC_NAME, 10)
        self.counter_seq = 0  # 발행 횟수 카운트 (원하면 제거 가능)
        self.get_logger().info("✅ Ready. Press SPACE to publish once. Press 'q' to quit.")

    def publish_once(self):
        self.counter_seq += 1

        msg = DbInfo()
        msg.registered = False
        msg.item_id = 21
        msg.counter = 2
        msg.visited_spots = [4, 3, 6, 2]
        msg.gate_id = 8

        self.pub.publish(msg)
        self.get_logger().info(
            f"📡 [{self.counter_seq}] published -> {TOPIC_NAME} | "
            f"registered={msg.registered}, item_id={msg.item_id}, counter={msg.counter}, "
            f"visited_spots={list(msg.visited_spots)}, gate_id={msg.gate_id}"
        )


def keyboard_loop(node: KeyDbInfoPub):
    """
    터미널에서 키 입력을 읽어서
    - 스페이스바: 1회 publish
    - q: 종료
    엔터 없이 동작하게 하려면 termios/tty가 필요한데,
    여기선 '엔터 없이'가 꼭 필요하지 않으면 가장 안정적인 방식(엔터 필요)로 제공.
    """
    while rclpy.ok():
        try:
            s = input()  # ✅ 엔터를 누르면 입력 확정됨
        except EOFError:
            break

        if s == "q":
            node.get_logger().info("👋 Quit requested. Shutting down.")
            rclpy.shutdown()
            break

        # 스페이스만 입력하고 엔터 치는 경우: " " 로 들어옴
        if s == " ":
            node.publish_once()
        else:
            node.get_logger().info("ℹ️ Press SPACE + Enter to publish, or q + Enter to quit.")


def main():
    rclpy.init()
    node = KeyDbInfoPub()

    t = threading.Thread(target=keyboard_loop, args=(node,), daemon=True)
    t.start()

    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
