#!/usr/bin/env python3
"""
- ROS2 토픽(/is_found)을 "계속" 구독(듣기)하는 노드이다.
- 로봇(또는 탐색 노드)이 탐색 결과를 토픽으로 보내면,
  이 파일은 그 결과를 받아서 SQLite DB의 item_lost 테이블 state를 업데이트한다.

즉,
  로봇 결과(찾음/못찾음)  --->  DB 상태(state) 변경
  /is_found(SearchResult) --->  item_lost.state = "회수" 또는 "분실"

웹(Flask)은 /search_status API로 DB state를 계속 조회(폴링)하므로,
이 파일이 DB state를 바꿔주면 웹 화면도 자동으로 성공/실패 화면으로 넘어갈 수 있다.
"""
import sqlite3
import rclpy
from rclpy.node import Node

from airport_guide_interfaces.msg import SearchResult  # 위 msg 기준
# DB 경로
DB_PATH = "/home/rokey/Desktop/amatta/sql/amatta.db"
# 토픽 이름
TOPIC_NAME = "/is_found"

"""
✅ 이 클래스의 역할(노드 역할)

- ROS2 노드(Node)를 하나 만든다.
- TOPIC_NAME(/is_found) 토픽을 구독한다.
- 메시지가 들어오면(cb 콜백 실행) DB에 상태를 반영한다.
"""
class ResultListener(Node):
    def __init__(self):
        super().__init__("search_result_listener")
        self.sub = self.create_subscription(SearchResult, TOPIC_NAME, self.cb, 10)    # /is_found에 대한 subscriber생성
        self.get_logger().info(f"✅ Listening: {TOPIC_NAME}")

        """
        ✅ cb 함수 역할(콜백 함수)

        - 토픽 메시지가 "올 때마다 자동으로 실행"되는 함수
        - 메시지에 담긴 (item_id, found)를 꺼낸다
        - found 값에 따라 DB state를 "회수" 또는 "분실"로 업데이트한다
        """
    def cb(self, msg: SearchResult):
        item_id = int(msg.item_id)
        found = bool(msg.found)

        new_state = "회수" if found else "분실"


        # ✅ 중요 로직: UPDATE 실행
        # - item_lost 테이블에서
        # - id가 item_id인 행을 찾아서
        # - state를 new_state로 변경한다
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.execute(
                "UPDATE item_lost SET state = ? WHERE id = ? AND state = '탐색중'",
                (new_state, item_id),
            )
            conn.commit()
            conn.close()

            self.get_logger().info(
                f"✅ lost_id={item_id} found={found} => state='{new_state}' (updated rows={cur.rowcount})"
            )
        except Exception as e:
            self.get_logger().error(f"DB update failed: {repr(e)}")


"""
✅ main 함수 역할(프로그램 시작/종료 흐름)

1) rclpy.init()         : ROS2 통신 초기화
2) ResultListener()     : 노드 생성(구독 시작 준비)
3) rclpy.spin(node)     : 무한 루프로 계속 토픽을 기다림(메시지 오면 cb 실행)
4) 종료 시 destroy/shutdown : 노드/ROS 정리
"""
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
