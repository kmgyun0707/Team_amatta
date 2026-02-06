import rclpy
from rclpy.node import Node
from detect_msg.msg import Rcinfo
from std_msgs.msg import String

from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator

class Move(Node):
    def __init__(self, navigator):
        super().__init__('move_node')
        self.get_logger().info(f'Move node init start')

        ns = self.get_namespace()

        self.yolo_sub = self.create_subscription(
            String,
            f'{ns}/yolo_result',
            self.web_sub_callback,
            10)

        self.subscription = self.create_subscription(
            Rcinfo,
            f'{ns}/detected_msg',
            self.detect_sub_callback,
            10)
    
        # 인지값 받아오는 서브스크라이버 콜백함수
    def detect_sub_callback(self, msg):
        self.detected = msg.detected
        self.goal = msg.goal  # geometry_msgs/PointStamped
        self.distance = msg.dist
        
        if self.detected:
            self.goal_x = self.goal.pose.position.x
            self.goal_y = self.goal.pose.position.y
            self.get_logger().info(
                f'Received: detected={self.detected}, '
                f'dist={self.distance}, '
                f'goal=({self.goal_x:.2f}, {self.goal_y:.2f})'
            )
        else:
            self.get_logger().info(f'Received: detected={self.detected}, dist={self.distance}')


def main():
    rclpy.init()

    # 노드 생성 (Move 클래스 내부에서 navigator를 쓰므로 일단 None으로 전달하거나 클래스 수정 필요)
    move_node = Move(navigator=None)

    try:
        rclpy.spin(move_node)
    except KeyboardInterrupt:
        move_node.get_logger().info('Shutdown requested via Ctrl+C.')
    finally:
        move_node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()