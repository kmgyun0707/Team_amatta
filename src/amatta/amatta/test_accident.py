import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

class TestRobot1Publisher(Node):
    def __init__(self):
        super().__init__('test_robot1_publisher')
        
        # [중요] 로봇 3의 Subscriber가 BEST_EFFORT이므로, 
        # Publisher도 반드시 BEST_EFFORT로 맞춰야 통신이 가능합니다.
        qos_best_effort = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # 토픽 발행 설정
        self.publisher_ = self.create_publisher(
            Pose, 
            '/robot1/simple_pose', 
            qos_best_effort
        )
        
        # 0.5초마다 발행 (2Hz)
        self.timer = self.create_timer(0.5, self.timer_callback)
        
        # 테스트용 좌표 변수 (x값만 이동시켜 봄)
        self.current_x = -1.83
        self.direction = 1  # 1: 증가, -1: 감소

    def timer_callback(self):
        msg = Pose()
        
        # 좌표 설정 (왔다 갔다 움직이도록 설정)
        msg.position.x = self.current_x
        msg.position.y = 2.34  # y는 고정
        msg.position.z = 0.0
        
        # 방향 설정 (필수 아님, 기본값 0)
        msg.orientation.w = 1.0

        # 토픽 발행
        self.publisher_.publish(msg)
        
        self.get_logger().info(f'Published Robot1 Pose: x={msg.position.x:.2f}, y={msg.position.y:.2f}')
        
        # 다음 좌표 계산 (0.0 ~ 5.0 사이를 왕복)
        self.current_x += (0.2 * self.direction)
        if self.current_x > 2.0:
            self.direction = -1
        elif self.current_x < 0.0:
            self.direction = 1

def main(args=None):
    rclpy.init(args=args)
    node = TestRobot1Publisher()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()