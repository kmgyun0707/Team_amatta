import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import PoseWithCovarianceStamped
from my_robot_interfaces.msg import DetectionResult

class DetectionBridge(Node):
    def __init__(self):
        super().__init__('detection_bridge')

        # 1. 구독자(Subscriber) 설정
        self.image_sub = self.create_subscription(
            Image,
            '/robot3/oakd/rgb/image_raw',
            self.image_callback,
            10)

        self.pose_sub = self.create_subscription(
            PoseWithCovarianceStamped,
            '/robot3/amcl_pose',
            self.pose_callback,
            10)

        # 2. 발행자(Publisher) 설정
        self.result_pub = self.create_publisher(
            DetectionResult,
            '/detected_object_info',
            10)

        self.current_image = None
        self.current_pose = None

        self.get_logger().info('Detection Bridge Node가 시작되었습니다.')

    def image_callback(self, msg):
        # 이미지가 들어오면 저장하고 발행 시도
        self.current_image = msg
        # self.get_logger().info('이미지 수신 중...') 
        self.check_and_publish()

    def pose_callback(self, msg):
        # 위치 정보가 들어오면 저장하고 발행 시도
        self.current_pose = msg.pose.pose 
        self.get_logger().info('위치 정보 수신 완료!') 
        self.check_and_publish()

    def check_and_publish(self):
        # 이미지와 위치 정보가 모두 존재할 때만 발행
        if self.current_image is not None and self.current_pose is not None:
            new_msg = DetectionResult()
            new_msg.image = self.current_image
            
            # PoseStamped 형식을 맞춰줍니다
            new_msg.pose.header = self.current_image.header
            new_msg.pose.pose = self.current_pose
            
            new_msg.class_name = "Lost_Item" 

            self.result_pub.publish(new_msg)
            self.get_logger().info('>>> [성공] 통합 데이터를 /detected_object_info로 발행했습니다!')
            
            # 데이터를 계속 보내고 싶다면 아래 초기화 코드는 주석 처리 유지
            # self.current_image = None
            # self.current_pose = None

def main(args=None):
    rclpy.init(args=args)
    node = DetectionBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('사용자에 의해 노드가 종료되었습니다.')
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()