#!/usr/bin/env python3
import sqlite3
import rclpy
from rclpy.node import Node

from airport_guide_interfaces.msg import SearchResult  # 위 msg 기준

DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"
TOPIC_NAME = "/search_result"

class ResultListener(Node):
    def __init__(self):
        super().__init__("search_result_listener")
        self.sub = self.create_subscription(SearchResult, TOPIC_NAME, self.cb, 10)
        self.get_logger().info(f"✅ Listening: {TOPIC_NAME}")

    def cb(self, msg: SearchResult):
        lost_id = int(msg.lost_id)
        found = bool(msg.found)

        new_state = "회수" if found else "분실"

        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.execute(
                "UPDATE item_lost SET state = ? WHERE id = ? AND state = '탐색중'",
                (new_state, lost_id),
            )
            conn.commit()
            conn.close()

            self.get_logger().info(
                f"✅ lost_id={lost_id} found={found} => state='{new_state}' (updated rows={cur.rowcount})"
            )
        except Exception as e:
            self.get_logger().error(f"DB update failed: {repr(e)}")

def main():
    rclpy.init()
    node = ResultListener()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
