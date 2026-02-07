# Robot 1: 분실물 등록 여부에 따른 모드 전환, 가이드 모드 코드
# [기능] DB에서 분실물 정보를 구독하여 등록 시 안내 모드, 미등록 시 탐색 모드(신호 발행) 수행
import rclpy
import time
from rclpy.node import Node
from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Bool
from nav2_simple_commander.robot_navigator import TaskResult
from airport_guide_interfaces.msg import DbInfo
from rclpy.executors import ExternalShutdownException

# INPUTS (topics):
# - /is_registered (airport_guide_interfaces/DbInfo): DB 등록 결과 수신. True면 가이딩 모드 시작, False면 탐색 모드 시작
# OUTPUTS (topics):
# - /search_mode (std_msgs/Bool): 등록 전 탐색 모드 요청(True) 퍼블리시.

class GuideToInfo(Node):
    def __init__(self):
        super().__init__('guide_to_info')
        self.navigator = TurtleBot4Navigator()
        self.registered = None
        self.handle_registration = False
        # 한번만 발행하기 위한 변수
        self.search_mode_published = False

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
            {'name': 'Counter',
            'pose': self.create_pose(-0.54, 3.64, 0.7177, 0.6963)}
        ]

        ################ 테스트 완료 후 setInitialPose만 남기기 ###############
        # 1. 초기화 및 Docking 상태 확인
        if not self.navigator.getDockedStatus():
            self.navigator.info('Docking before initialising pose')
            self.navigator.dock()

        # 2. 초기 위치 설정
        # initial_pose = self.navigator.getPoseStamped([0.0, 3.0], TurtleBot4Directions.NORTH)
        initial_pose = self.navigator.getPoseStamped([0.0, 0.0], TurtleBot4Directions.NORTH)        # robot3으로 실행 시
        self.navigator.setInitialPose(initial_pose)

        # 3. Nav2 활성화 대기 및 Undock
        self.navigator.info('Before Nav')
        self.navigator.waitUntilNav2Active()
        self.navigator.info('After Nav')
        self.navigator.undock()

    def timer_callback(self):       # DB의 분실물 여부 퍼블리시
        # msg = Bool()
        # if not self.registered:
        #     msg.data = True
        # else:
        #     msg.data = False
        
        # self.publisher.publish(msg)
        self.get_logger().info(f'publish*********{self.registered}')
        if self.registered is None:
            self.get_logger().info(f'no publish*********')
            return 
        if not self.search_mode_published:
            msg = Bool()
            msg.data = not self.registered
            self.publisher.publish(msg)
            self.search_mode_published = True
            self.timer.cancel()

        # msg = Bool()
        # msg.data = not self.registered
        # self.publisher.publish(msg)

    
    def db_callback(self, msg):
        if self.handle_registration:
            return
        self.registered = msg.registered
        self.get_logger().info(f"Received DB Info: registered={self.registered}")
        # 분실물이 있으면 분실물 보관소로 이동
        if self.registered:
            self.get_logger().info(f'Guide to Counter...')
            self.handle_registration = True
            self.navigator.startToPose(self.target_pose[0]['pose'])

            while not self.navigator.isTaskComplete():
                if not rclpy.ok(): 
                    return
                time.sleep(0.1)

            result = self.navigator.getResult()# 이 경우에만 코드 종료되도록 수정 필요
            if result == TaskResult.SUCCEEDED:      
                self.navigator.info(f'Arrived at entrance!')
                rclpy.shutdown()
            elif result == TaskResult.CANCELED:
                self.navigator.info(f'Navigation to entrance was canceled.')
            elif result == TaskResult.FAILED:
                self.navigator.error(f'Failed to reach entrance.')



    # x,y,방향 값을 받아 PostStamped 형식으로 변환
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
    guide = GuideToInfo()

    try:
        while rclpy.ok():
            rclpy.spin(guide)
            
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
        
    if rclpy.ok():
            guide.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()