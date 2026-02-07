import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import PoseWithCovarianceStamped
import time
import random

class MockRobotSender(Node):
    def __init__(self):
        super().__init__('mock_robot_sender')

        # 로봇 이름 설정 (필요하면 robot3 등으로 변경 가능)
        self.robot_name = 'robot3'

        # 1. 위치(Pose) 발행자 (amcl_pose)
        self.pose_pub = self.create_publisher(
            PoseWithCovarianceStamped, 
            f'/{self.robot_name}/amcl_pose', 
            10
        )
        
        # 2. 이미지(Image) 발행자 (lost_item)
        self.image_pub = self.create_publisher(
            Image, 
            f'/{self.robot_name}/lost_item', 
            10
        )

        # 타이머 설정
        # 0.5초마다 위치 업데이트 (로봇이 움직이는 척)
        self.pose_timer = self.create_timer(0.5, self.publish_fake_pose)
        # 3초마다 이미지 전송 (물건 찾은 척)
        self.image_timer = self.create_timer(3.0, self.publish_fake_image)

        self.get_logger().info(f'[{self.robot_name}] 가짜 로봇 시뮬레이터 시작!')
        self.get_logger().info('>>> 위치 전송 중...')
        self.get_logger().info('>>> 이미지 발사 중...')

    def publish_fake_pose(self,):
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.get_clock().now().to_msg()
        
        # 위치를 조금씩 랜덤으로 바꿔서 생동감 주기
        msg.pose.pose.position.x = 5.0 + random.uniform(-0.5, 0.5)
        msg.pose.pose.position.y = 3.0 + random.uniform(-0.5, 0.5)
        msg.pose.pose.orientation.w = 1.0
        
        self.pose_pub.publish(msg)
        # (로그가 너무 많이 뜨면 정신없으니 위치 전송 로그는 생략)

    def publish_fake_image(self):
        msg = Image()
        msg.header.frame_id = 'camera_link'
        msg.header.stamp = self.get_clock().now().to_msg()
        
        # 2x2 픽셀, RGB8 포맷 (빨간색 점)
        msg.height = 2
        msg.width = 2
        msg.encoding = 'rgb8'
        msg.step = 6 # width(2) * 3 bytes
        # 빨간색 픽셀 4개 데이터 [R, G, B, R, G, B, ...]
        msg.data = [255, 0, 0, 255, 0, 0, 255, 0, 0, 255, 0, 0]

        self.image_pub.publish(msg)
        self.get_logger().info(f' 이미지 전송 완료 (DB에서 확인하세요)')

def main(args=None):
    rclpy.init(args=args)
    node = MockRobotSender()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('테스트 종료 👋')
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()