import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import PoseWithCovarianceStamped
from my_robot_interfaces.msg import DetectionResult

class DetectionBridge(Node):
    def __init__(self):
        super().__init__('detection_bridge')

        # 1. 구독자(Subscriber) 설정
        # [변경] 원본 영상 대신 팀원이 발행하는 '탐지된 이미지'를 트리거로 사용합니다.
        self.image_sub = self.create_subscription(
            Image,
            '/robot3/lost_item',  # 탐지 시에만 발행되는 토픽
            self.image_callback,
            10)

        # 위치 정보는 로봇이 움직일 때마다 조용히 업데이트만 해둡니다.
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

        self.get_logger().info('이벤트 기반 Detection Bridge(v2)가 시작되었습니다.')

    def pose_callback(self, msg):
        # 위치 정보는 계속 업데이트하여 '최신 상태'를 유지합니다.
        self.current_pose = msg.pose.pose 
        # (불필요한 로그 삭제: 탐지 시에만 로그를 찍는 것이 깔끔합니다)

    def image_callback(self, msg):
        # [중요] 팀원의 YOLO 노드에서 탐지 이미지가 들어오는 순간 실행됩니다.
        self.current_image = msg
        self.get_logger().info('● 객체 탐지 이벤트 수신!')
        self.check_and_publish()

    def check_and_publish(self):
        # 탐지 영상과 현재 위치가 모두 확보되었는지 확인
        if self.current_image is not None and self.current_pose is not None:
            new_msg = DetectionResult()
            new_msg.image = self.current_image
            
            # 탐지된 시점의 헤더 정보를 유지합니다.
            new_msg.pose.header = self.current_image.header
            new_msg.pose.pose = self.current_pose
            
            # TODO: 팀원이 클래스명을 별도로 준다면 그 값을 연결하세요.
            # 지금은 기본값으로 설정합니다.
            new_msg.class_name = "Detected_Object" 

            self.result_pub.publish(new_msg)
            self.get_logger().info('>>> [DB용] 탐지 데이터 통합 발행 완료!')
            
            # 다음 탐지 이벤트를 위해 이미지는 초기화합니다.
            self.current_image = None
        else:
            if self.current_pose is None:
                self.get_logger().warn('탐지 영상은 왔으나 로봇 위치(AMCL)가 아직 없습니다.')

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