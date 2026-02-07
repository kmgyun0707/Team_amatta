import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import PoseWithCovarianceStamped

# 우리가 만든 인터페이스 2개를 모두 가져옵니다.
from my_robot_interfaces.msg import DetectionResult # DB 저장용
from airport_guide_interfaces.msg import DetectionInfo  # Navigator 알림용

class DetectionBridge(Node):
    def __init__(self):
        super().__init__('detection_bridge')

        # 로봇 이름을 파라미터로 받습니다 (기본값: robot3)
        self.declare_parameter('robot_name', 'robot3')
        self.robot_name = self.get_parameter('robot_name').value

        # 토픽 이름 자동 설정
        # 1. 트리거: 팀원이 만든 '/robot3/lost_item' (탐지됐을 때만 들어오는 이미지)
        topic_trigger = f'/{self.robot_name}/lost_item'
        # 2. 위치: '/robot3/amcl_pose' (로봇의 현재 위치)
        topic_pose = f'/{self.robot_name}/amcl_pose'
        
        # 3. 보낼 곳(DB): '/detected_object_info' (공용)
        topic_db = '/detected_object_info'
        # 4. 보낼 곳(Nav): '/robot3/is_detected' (네비게이터 팀원용)
        topic_nav = f'/{self.robot_name}/is_detected'

        self.get_logger().info(f'[{self.robot_name}] 통합 브릿지 노드 시작 (DB + Nav 연동)')

        # 구독자 (Subscriber)
        self.image_sub = self.create_subscription(
            Image, topic_trigger, self.image_callback, 10)
        self.pose_sub = self.create_subscription(
            PoseWithCovarianceStamped, topic_pose, self.pose_callback, 10)

        # 발행자 (Publisher)
        self.db_pub = self.create_publisher(DetectionResult, topic_db, 10)
        self.nav_pub = self.create_publisher(DetectionInfo, topic_nav, 10)

        self.current_pose = None

    def pose_callback(self, msg):
        # 로봇 위치만 계속 업데이트 (여기선 발행 안 함)
        self.current_pose = msg.pose.pose

    def image_callback(self, msg):
        # 팀원의 YOLO가 물체를 찾아서 이미지를 보내면 실행됩니다!
        self.get_logger().info(f'!!! 탐지 신호 수신 ({self.robot_name}) !!!')
        
        if self.current_pose is not None:
            # ---------------------------------------------------
            # 1. DB로 보낼 데이터 (DetectionResult)
            # ---------------------------------------------------
            db_msg = DetectionResult()
            db_msg.image = msg
            db_msg.pose.header = msg.header
            db_msg.pose.pose = self.current_pose
            db_msg.class_name = "Lost_Item"
            self.db_pub.publish(db_msg)

            # ---------------------------------------------------
            # 2. Navigator로 보낼 데이터 (DetectionInfo)
            # ---------------------------------------------------
            nav_msg = DetectionInfo()
            nav_msg.detected = True  # "찾았다!" 신호
            
            # 목표 위치(goal) 채우기
            nav_msg.goal.header = msg.header
            nav_msg.goal.pose = self.current_pose # 현재 위치를 목표점으로 전달
            
            self.nav_pub.publish(nav_msg)
            
            self.get_logger().info('>>> 전송 완료: [1]DB저장 [2]Nav알림')
        else:
            self.get_logger().warn('탐지는 되었으나 위치 정보(AMCL)가 없어 전송 실패')

def main(args=None):
    rclpy.init(args=args)
    node = DetectionBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()