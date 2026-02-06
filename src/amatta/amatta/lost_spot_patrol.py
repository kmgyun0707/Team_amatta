# robot 3 구동하는 코드: 사용자의 이동 경로를 제외한 주요 구역 탐색 및 로봇 1이 가까워 지면 정지

import rclpy
from rclpy.node import Node
import time
import math
import itertools
from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped,Twist
from nav2_simple_commander.robot_navigator import TaskResult
from std_msgs.msg import Bool
from airport_guide_interfaces.msg import DbInfo,DetectionInfo

# Multi Thread
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
import threading

# INPUTS (topics):
# - /visited_spot (std_msgs/Int32MultiArray) : 사용자 이동 장소에 대한 번호 리스트 구독
# - /search_mode (std_msgs/Bool) : 탐색 모드 실행 (False면 대기/ True면 탐색) 요청 구독
# - /is_detected (std_msgs/Bool) : 분실물이 탐지 되었는지 bool 구독
# - /robot1/amcl_pose (geometry_msgs/PoseWithCovarianceStamped) : 로봇 1의 현재 위치 구독
# - /robot3/amcl_pose (geometry_msgs/PoseWithCovarianceStamped) : 로봇 2의 현재 위치 구독
# OUTPUTS (topics):
# - /robot3/cmd_vel (geometry_msgs/Twist) : 로봇 3의 속도를 제어하기 위해 로봇의 /cmd_vel 발행


class LostItemPatrol(Node):
    def __init__(self):
        super().__init__('lost_item_patrol')
        # 콜백 그룹 생성 (이 그룹에 속한 콜백들은 병렬 실행 가능)
        self.callback_group = ReentrantCallbackGroup()

        self.navigator = TurtleBot4Navigator()

        # 토픽 수신 여부와 데이터를 저장할 변수 초기화
        self.visited_spot = []          # 이동할 경로 리스트
        self.registered = False   # db로부터 토픽을 수신했는지 여부
        self.search_mode = False        # 탐색 모드 여부
        self.is_detected = False        # 분실물을 인지했는지 여부
        self.robot1_pose = None
        self.robot2_pose = None
        self.current_pose = None        # 로봇의 현재 위치값
        ns =self.get_namespace

        # 사용자가 이동한 장소에 대한 장소 번호 리스트를 담은 토픽 구독
        self.subscription = self.create_subscription(
            DbInfo,
            f'{ns}/is_registered',
            self.topic_callback,
            10,
            callback_group=self.callback_group)

        # guide_to_info에서 발행하는 탐색 모드 토픽 구독
        self.search_mode_sub = self.create_subscription(
            Bool,
            f'{ns}/search_mode',
            self.search_mode_callback,
            10,
            callback_group=self.callback_group)
        
        # 로봇 3의 속도를 제어하기 위해 로봇의 /cmd_vel 발행
        self.cmd_vel_pub = self.navigator.create_publisher(
            Twist,
            f'{ns}/cmd_vel',
            10,
            callback_group=self.callback_group)

        # 로봇 1,2의 현재 위치 각각 구독 -> 로봇 간 거리 계산에 사용
        self.robot1_sub = self.create_subscription(
            PoseWithCovarianceStamped,
            '/robot1/amcl_pose',
            self.robot1_pose_callback,
            10,
            callback_group=self.callback_group)
        
        self.robot2_sub = self.create_subscription(
            PoseWithCovarianceStamped,
            '/robot3/amcl_pose',
            self.pose_callback,
            10,
            callback_group=self.callback_group)

        # 분실물이 감지 되었는지 Bool 값 토픽 구독
        self.detection_sub = self.create_subscription(
            DetectionInfo,
            f'{ns}/is_detected',
            self.detection_callback,
            10,
            callback_group=self.callback_group)
        

        # 목표 지점 정의 (robot 3 좌표 기준)
        self.goal_options = [
            # 0 입구 (Entrance)
            {'name': 'Entrance',
             'pose': self.create_pose(-3.26, 3.77, 0.9881, 0.1536)},

            # 1 은행 (Bank)
            {'name': 'Bank',
             'pose': self.create_pose(-2.08, 3.45, 0.4327, 0.9015)},

            # 2 카운터 (Counter)
            {'name': 'Counter',
             'pose': self.create_pose(-0.584, 3.64, -0.7689, 0.6394)},

            # 3 벤치1 (Bench 1)
            {'name': 'Bench_1',
             'pose': self.create_pose(-0.791, 2.19, -0.7689, 0.6394)},

            # 4 벤치2 (Bench 2)
            {'name': 'Bench_2',
             'pose': self.create_pose(-0.672, 0.615, 0.58, 0.8146)},

            # 5 여자화장실 (Ladies Room)
            {'name': 'Ladies_Room',
             'pose': self.create_pose(-0.547, -0.636, -0.1166, 0.9931)},

            # 6 면세점 (Duty Free)
            {'name': 'Duty_Free',
             'pose': self.create_pose(-2.35, 0.799, 0.7177, 0.6963)},

            # 7 남자화장실 (Mens Room)
            {'name': 'Mens_Room',
             'pose': self.create_pose(-3.16, 2.58, 0.7177, 0.6963)}
        ]
        self.gate_options = [
            # 0번 인덱스: Gate 1
            {'name': 'Gate_1',
             'pose': self.create_pose(-0.76, -1.59, 0.9881, 0.1536)},

            # 1번 인덱스: Gate 2
            {'name': 'Gate_2',
             'pose': self.create_pose(-2.18, -1.26, -0.7512, 0.66)},
        ]

         # 1. 초기화 및 Docking 상태 확인
        if not self.navigator.getDockedStatus():
            self.navigator.info('Docking before initialising pose')
            self.navigator.dock()

        # 2. 초기 위치 설정
        initial_pose = self.navigator.getPoseStamped([0.0, 0.0], TurtleBot4Directions.NORTH)
        self.navigator.setInitialPose(initial_pose)

        # 3. Nav2 활성화 대기 및 Undock
        self.navigator.waitUntilNav2Active()
        self.navigator.undock()
    
    # 탐색 모드 전환(True면 탐색, False면 대기)
    def search_mode_callback(self, msg):
        self.search_mode = msg.data
        if self.search_mode:
            self.get_logger().info("Search mode activated! Ready to patrol.")
        else:
            self.get_logger().info("Search mode deactivated. Waiting...")
            
    # visited_spot 토픽이 들어오면 실행 사용자 이동 내역을 리스트 형태로 저장
    ################ 추후 DBInfo Sub으로 수정 필요 ###################
    def topic_callback(self, msg):
        self.get_logger().info(f"Topic Received! Data: {msg.visited_spots}")
        self.visited_spot_raw = list(msg.visited_spots)
        self.gate_id = msg.gate_id - 8      # 게이트 1, 2이 8, 9로 들어오기 때문에 gate_options 인덱스에 맞게 빼줌
        self.registered = msg.registered

    # 로봇 1 : amcl 토픽중 좌표와 방향만 저장
    def robot1_pose_callback(self, msg):
        self.current_pose = PoseStamped()
        self.current_pose.header = msg.header
        self.robot1_pose = msg.pose.pose
    
    # 로봇 2 : amcl 토픽중 좌표와 방향만 저장
    def pose_callback(self, msg):
        self.current_pose = PoseStamped()
        self.current_pose.header = msg.header
        self.current_pose.pose = msg.pose.pose

        self.robot2_pose = msg.pose.pose
    
    # 분실물을 발견했는지 실시간 저장
    def detection_callback(self, msg):
        self.is_detected = msg.detected
        self.goal = msg.goal
    
    # 로봇1이 얼마나 가까이에 있는지 확인
    def is_robot1_nearby(self, threshold=1.0):      # threshold: 안전 거리
        if self.robot1_pose is None or self.robot2_pose is None:
            self.get_logger().error(f'로봇 위치 못 받아옴')
            return False

        dist = math.sqrt(       # 로봇 간 직선 거리 계산
            (self.robot1_pose.position.x - self.robot2_pose.position.x)**2 +
            (self.robot1_pose.position.y - self.robot2_pose.position.y)**2
        )
        self.get_logger().info(f'dist: {dist}, dist<threshold: {dist < threshold}')
        return dist < threshold

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

    # 목표 지점 사이 직선거리
    def get_distance(self, pose1, pose2):
        x1 = pose1.pose.position.x
        y1 = pose1.pose.position.y
        x2 = pose2.pose.position.x
        y2 = pose2.pose.position.y
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    # Brute 알고리즘으로 사용자가 입력한 이동 경로 중 최단 경로 탐색
    def find_best_route_brute_force(self, start_pose, spots_indices):
        min_distance = float('inf')
        best_order = []
        
        # 순열 생성 (모든 방문 순서 고려)
        possible_paths = itertools.permutations(spots_indices)
        
        # 순서 조합을 하나씩 실제로 주행했을 때 거리 계산
        for path in possible_paths:
            current_distance = 0.0
            current_pose = start_pose
            
            for idx in path:
                target_pose = self.goal_options[idx]['pose']
                dist = self.get_distance(current_pose, target_pose)
                current_distance += dist
                current_pose = target_pose
            
            if current_distance < min_distance:
                min_distance = current_distance
                best_order = list(path)
                
        return best_order, min_distance

    # 로봇 정지
    def stop_robot(self):
        stop_msg = Twist()
        stop_msg.linear.x = 0.0
        stop_msg.linear.y = 0.0
        stop_msg.linear.z = 0.0
        stop_msg.angular.x = 0.0
        stop_msg.angular.y = 0.0
        stop_msg.angular.z = 0.0
        
        # 확실하게 멈추기 위해 여러 번 publish
        for _ in range(10):
            self.cmd_vel_pub.publish(stop_msg)
            time.sleep(0.01)

    def run_patrol(self):
        # 사용자가 방문한 장소을 제외한 목표 지점 결정
        all_indices = list(range(len(self.goal_options)))
        self.visited_spot = [idx for idx in all_indices if idx not in self.visited_spot_raw]
        
        print(f"\n최종 방문할 장소 인덱스: {self.visited_spot}")

        # 사용자 이동 내역이 없을 경우 종료
        if not self.visited_spot:
            self.navigator.info("No targets selected. Exiting.")
            return

        self.navigator.info('Starting patrol service...')

        # 현재 위치가 아직 없으면 잠시 대기
        if self.current_pose is None:
            self.get_logger().warn('Waiting for initial pose...')
            time.sleep(1.0)

            # 대기해도 현재 위치 못 받아올 경우, navigator로부터 위치값 가져오기
            if self.current_pose is None:
                self.get_logger().warn('No Pose')
                self.current_pose = self.navigator.getPoseStamped([0,0], TurtleBot4Directions.NORTH)
        
        start_pose = self.current_pose
        best_route, _ = self.find_best_route_brute_force(start_pose, self.visited_spot) # 최적 경로 계산

        path_names = [self.goal_options[i]['name'] for i in best_route]
        self.navigator.info(f'Optimized Route: {path_names}')

        # 주행 시작
        for index in best_route:
            target_name = self.goal_options[index]['name']
            target_pose = self.goal_options[index]['pose']

            gate_name = self.gate_options[self.gate_id]['name']
            gate_pose = self.gate_options[self.gate_id]['pose']

            # 로봇 1이 로봇2와의 거리가 1.5미터 이내면 대기
            while self.is_robot1_nearby(1.5):
                self.navigator.info("Robot 1 is too close! Waiting...")
                time.sleep(1.0)

            self.navigator.info(f'Navigating to {target_name}...')
            self.navigator.startToPose(target_pose)

            while not self.navigator.isTaskComplete():

                # 분실물 발견 시 정지
                if self.is_detected:
                    self.navigator.cancelTask()
                    self.stop_robot()       # 추후 접근으로 구현 필요
                    return

                # 로봇1,2간의 거리가 1미터 이내 일때
                if self.is_robot1_nearby(1.0):
                    self.navigator.info("Robot 1 approaching! Yielding...")
                    self.navigator.cancelTask()
                    self.stop_robot()

                    # 로봇간의 거리가 1미터 이상이 될 때 까지 대기
                    while self.is_robot1_nearby(1.0):
                        self.navigator.info("Robot 1 approaching! Yielding...")
                        time.sleep(1.0)
                    
                    self.navigator.info("Resuming path...")
                    self.navigator.startToPose(target_pose)
                time.sleep(0.1)

            result = self.navigator.getResult()
            if result == TaskResult.SUCCEEDED:
                self.navigator.info(f'Arrived at {target_name}!')
                time.sleep(1.0)

                # 게이트로 이동
                self.get_logger().info(f'go to {gate_name}')
                self.navigator.startToPose(gate_pose)

            elif result == TaskResult.CANCELED:
                self.navigator.info(f'Navigation to {target_name} was canceled.')
            elif result == TaskResult.FAILED:
                self.navigator.error(f'Failed to reach {target_name}.')

        # 분실물이 발견이 되면 DB 업로드 (추후 추가 예정)
        if not self.is_detected:
            self.navigator.info('DB Upload')
            # /is_found (Bool) 토픽 False로 퍼블리시
        self.navigator.info('All tasks completed. Returning to dock...')

def main(args=None):
    rclpy.init(args=args)
    
    patrol_robot = LostItemPatrol()

    # [핵심 변경] Executor를 생성하고 Node를 추가
    executor = MultiThreadedExecutor()
    executor.add_node(patrol_robot)

    # [핵심 변경] Executor를 별도 쓰레드(Daemon)에서 실행
    # 이렇게 하면 spin()이 백그라운드에서 계속 돌며 콜백(위치 수신, 탐지 등)을 처리합니다.
    executor_thread = threading.Thread(target=executor.spin, daemon=True)
    executor_thread.start()
    
    try:
        patrol_robot.get_logger().info("Main Loop Started. Waiting for command...")
        while rclpy.ok():
            patrol_robot.get_logger().info(f'search mode: {patrol_robot.search_mode}')
            
            # Guide 노드로부터 search mode 받고, DB로부터 사용자 이동 경로 받으면 탐색 시작
            if patrol_robot.search_mode and patrol_robot.registered:
                patrol_robot.run_patrol()


                patrol_robot.registered = False 
                # 탐색이 끝나면 프로그램 종료
                patrol_robot.search_mode = False 
                patrol_robot.get_logger().info("Patrol finished. Waiting for next command or Exit.")
                break   # 한 번만 하고 끌거면 break 사용
                
    except KeyboardInterrupt:
        pass
    finally:
        patrol_robot.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()