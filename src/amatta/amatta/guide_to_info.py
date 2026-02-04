# robot 1 구동하는 코드: db에서 분실물 관련 토픽 구독해 보관소에 분실물 유무에 따른 가이드 모드 및 탐색 모드
import rclpy
from rclpy.node import Node
from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Bool
from airport_guide_interfaces.msg import DbInfo


class GuideToInfo(Node):
    def __init__(self):
        super().__init__('guide_to_info')
        self.navigator = TurtleBot4Navigator()
        self.registered = False

        # 토픽으로 탐색 모드 여부(True = 탐색모드 시작) 발행
        self.publisher = self.create_publisher(
            Bool,
            '/search_mode',
            10
        )

        # db에서 DbInfo 타입의 분실물의 유무 토픽 구독
        self.subscription = self.create_subscription(
            DbInfo,
            '/is_registered',
            self.db_callback,
            10
        )
        
        self.timer = self.create_timer(0.5, self.timer_callback)


        # 4. 목표 지점 정의
        self.target_pose = [
            # 분실물 보관소 좌표
            {'name': 'Entrance',
            'pose': self.create_pose(-3.26, 3.71, 0.9881, 0.1536)}
        ]

        ################ 테스트 완료 후 초기 위치만 남기기 ###############
        # 1. 초기화 및 Docking 상태 확인
        if not self.navigator.getDockedStatus():
            self.navigator.info('Docking before initialising pose')
            self.navigator.dock()

        # 2. 초기 위치 설정
        initial_pose = self.navigator.getPoseStamped([0.0, 3.0], TurtleBot4Directions.NORTH)
        self.navigator.setInitialPose(initial_pose)

        # 3. Nav2 활성화 대기 및 Undock
        self.navigator.waitUntilNav2Active()
        self.navigator.undock()

    def timer_callback(self):
        if not self.registered:
            msg = Bool()
            msg.data = True
        
        self.publisher.publish(msg)

    
    def db_callback(self, msg):
        self.registered = msg.registered
        if self.registered:
            self.get_logger().info(f'Guide to Counter...')
            self.navigator.startToPose(self.target_pose)


        
    def create_pose(self, x, y, z_orient, w_orient):
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.navigator.get_clock().now().to_msg()
        pose.pose.position.x = float(x)
        pose.pose.position.y = float(y)
        pose.pose.position.z = 0.0
        pose.pose.orientation.x = 0.0
        pose.pose.orientation.y = 0.0
        pose.pose.orientation.z = float(z_orient)
        pose.pose.orientation.w = float(w_orient)
        return pose

def main(args=None):
    rclpy.init(args=args)
    
    # 클래스 인스턴스 생성 및 실행
    guide = GuideToInfo()

    try:
        # [핵심 수정] 데이터가 들어올 때까지 Node를 Spin(대기) 시킵니다.
        while rclpy.ok():
            rclpy.spin(guide)
            
    except KeyboardInterrupt:
        pass
        
    finally:
        guide.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()