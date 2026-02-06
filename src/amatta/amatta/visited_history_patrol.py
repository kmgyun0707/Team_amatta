# robot 1 구동하는 코드: 사용자가 입력한 이동 경로를 따라 최단 경로 탐색

import rclpy
from rclpy.node import Node
import time
import math
import itertools
from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped,Twist, Pose
from nav2_simple_commander.robot_navigator import TaskResult
from std_msgs.msg import Bool
from airport_guide_interfaces.msg import DbInfo,DetectionInfo

from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
import threading

from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy


# INPUTS (topics):
# - /visited_spot (std_msgs/Int32MultiArray) : 사용자 이동 장소에 대한 번호 리스트 구독
# - /search_mode (std_msgs/Bool) : 탐색 모드 실행 (False면 대기/ True면 탐색) 요청 구독
# - /is_detected (std_msgs/Bool) : 분실물이 탐지 되었는지 bool 구독
# - /robot1/amcl_pose (geometry_msgs/PoseWithCovarianceStamped) : 로봇 1의 현재 위치 구독
# OUTPUTS (topics):
# - /robot1/cmd_vel (geometry_msgs/Twist) : 로봇 1의 속도를 제어하기 위해 로봇의 /cmd_vel 발행


class VisitedHistoryPatrol(Node):
    def __init__(self):
        super().__init__('visited_history_patrol')
        # 콜백 그룹 생성 (이 그룹에 속한 콜백들은 병렬 실행 가능)
        self.callback_group = ReentrantCallbackGroup()

        self.navigator = TurtleBot4Navigator()

        # 토픽 수신 여부와 데이터를 저장할 변수 초기화
        self.visited_spot = []          # 이동할 경로 리스트
        self.registered = False         # db로부터 토픽을 수신했는지 여부
        self.search_mode = False        # 탐색 모드 여부
        self.detected_robot3 = False        # 분실물을 인지했는지 여부
        self.detected_robot1 = False
        self.current_pose = None 
        ns =self.get_namespace()

        # BEST_EFFORT 설정 정의
        # - Reliability: BEST_EFFORT (전송 속도 우선, 유실 허용)
        # - History: KEEP_LAST (최신 데이터 유지를 위해 필수)
        # - Depth: 10 (버퍼 크기)
        qos_best_effort = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        ### Subscribers
        # guide_to_info에서 발행하는 탐색 모드 토픽 구독
        self.search_mode_sub = self.create_subscription(
            Bool,
            '/search_mode',
            self.search_mode_callback,
            10,
            callback_group=self.callback_group)
        
        # 사용자가 이동한 장소에 대한 장소 번호 리스트를 담은 토픽 구독
        self.subscription = self.create_subscription(
            DbInfo,
            '/is_registered',
            self.topic_callback,
            10,
            callback_group=self.callback_group)

        # 로봇 1의 현재 위치 구독 -> 경로 생성 사용
        self.subscription_pose = self.create_subscription(
            PoseWithCovarianceStamped,
            f'{ns}/amcl_pose',
            self.pose_callback,
            qos_best_effort,
            callback_group=self.callback_group)

        # 분실물이 감지 되었는지 Bool 값 토픽 구독 (자기 자신이 분실물을 찾았는지 확인)
        self.detection_robot1_sub = self.create_subscription(
            DetectionInfo,
            '/robot1/is_detected',
            self.detection_robot1_callback,
            10,
            callback_group=self.callback_group)
        
        # 분실물이 감지 되었는지 Bool 값 토픽 구독 (다른 로봇이 분실물을 찾았는지 확인)
        self.detection_robot3_sub = self.create_subscription(
            DetectionInfo,
            '/robot3/is_detected',
            self.detection_robot3_callback,
            10,
            callback_group=self.callback_group)
        
        ### Publisher
        ## 로봇1의 좌표 발행
        self.robot1_pose_pub = self.create_publisher(
            Pose, 
            '/robot1/simple_pose', 
            qos_best_effort
        )

        # 로봇 1의 속도를 제어하기 위해 로봇의 /cmd_vel 발행 -> 로봇이 분실물 발견 시 정지
        self.cmd_vel_pub = self.navigator.create_publisher(
            Twist,
            f'{ns}/cmd_vel',
            10,
            callback_group=self.callback_group
        )

        self.is_found_pub = self.navigator.create_publisher(
            Bool,
            f'{ns}/is_found',
            10,
            callback_group=self.callback_group
        )
        # self.timer = self.create_timer(0.5, self.timer_callback)
        # 목표 지점 정의 (robot 1 좌표 기준)
        self.goal_options = [
            # 0 입구 (Entrance)
            {'name': 'Entrance',
            'pose': self.create_pose(-3.26, 3.71, 0.9881, 0.1536)},

            # 1 은행 (Bank)
            {'name': 'Bank',
            'pose': self.create_pose(-2.39, 3.15, 0.4327, 0.9015)},

            # 2 카운터 (Counter)
            {'name': 'Counter',
            'pose': self.create_pose(-0.54, 3.64, 0.7177, 0.6963)},

            # 3 벤치1 (Bench 1)
            {'name': 'Bench_1',
            'pose': self.create_pose(-0.54, 2.12, -0.7689, 0.6394)},

            # 4 벤치2 (Bench 2)
            {'name': 'Bench_2',
            'pose': self.create_pose(-0.83, 0.80, 0.58, 0.8146)},

            # 5 여자화장실 (Ladies Room)
            {'name': 'Ladies_Room',
            'pose': self.create_pose(-0.486, -0.75, -0.1166, 0.9931)},

            # 6 면세점 (Duty Free)
            {'name': 'Duty_Free',
            'pose': self.create_pose(-1.99, 0.82, -0.9927, 0.1203)},

            # 7 남자화장실 (Mens Room)
            {'name': 'Mens_Room',
            'pose': self.create_pose(-3.29, 2.6, 0.9980, 0.0631)}
        ]
        self.gate_options = [
            # 0 Gate 1
            {'name': 'Gate_1',
            'pose': self.create_pose(-0.60, -1.31, -0.6276, 0.7785)},

            # 1 Gate 2
            {'name': 'Gate_2',
            'pose': self.create_pose(-2.13, -1.37, -0.7512, 0.66)},
        ]

    # 가이드 노드로부터 탐색 모드인지 서브스크라이브
    def search_mode_callback(self, msg):
        self.search_mode = msg.data
        if self.search_mode:
            self.get_logger().info("Search mode activated! Ready to patrol.")
        else:
            self.get_logger().info("Search mode deactivated. Waiting...")
            
    # visited_spot 토픽이 들어오면 실행 / 사용자 이동 내역을 리스트 형태로 저장
    def topic_callback(self, msg):
        self.visited_spot= list(msg.visited_spots)
        self.gate_id = msg.gate_id - 8      # 게이트 1, 2이 8, 9로 들어오기 때문에 gate_options 인덱스에 맞게 빼줌
        self.registered = msg.registered
        self.get_logger().info(f"Topic Received! gate : {self.gate_id}, registered : {self.registered}")
        self.get_logger().info(f"Topic Received! visited spot : {self.visited_spot}")

    # amcl_pose토픽에서 좌표와 방향만 필요하기 때문에 PoseStamped 규격으로 필요한 정보만 저장
    def pose_callback(self, msg):
        self.current_pose = PoseStamped()
        self.current_pose.header = msg.header
        self.current_pose.pose = msg.pose.pose
        if self.current_pose is not None:
            self.get_logger().info(f"Pose Received!")
            self.robot1_pose_pub.publish(self.current_pose.pose)

    # def timer_callback(self): 
    #     if self.current_pose is None:
    #         return
    #     self.robot1_pose_pub.publish(self.current_pose.pose)

    # 분실물을 발견했는지 실시간 저장
    def detection_robot1_callback(self, msg):
        self.detected_robot1 = msg.detected
        self.goal = msg.goal

    def detection_robot3_callback(self, msg):
        self.detected_robot3 = msg.detected

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

    # 로봇 정지 -> 인지 시 정지 (추후 정지 후 접근으로 수정 예정)
    def stop_robot(self):
        stop_msg = Twist()
        stop_msg.linear.x = 0.0
        stop_msg.linear.y = 0.0
        stop_msg.linear.z = 0.0
        stop_msg.angular.x = 0.0
        stop_msg.angular.y = 0.0
        stop_msg.angular.z = 0.0
        
        # 확실하게 멈추기 위해 여러 번 publish
        for _ in range(2):
            self.get_logger().info("in stop robot pub*****")
            self.cmd_vel_pub.publish(stop_msg)
            time.sleep(1)

    # 최단 경로 주행
    def run_patrol(self):
        self.navigator.info('Initializing User History Tracer...')

        # 사용자 이동 내역이 없을 경우 종료
        if not self.visited_spot:
            self.navigator.info("No visited_spot provided. Exiting.")
            return

        ################333
        # timeout = 3.0  # 3초 타임아웃
        # start_time = time.time()
        # while self.current_pose is None:
        #     if time.time() - start_time > timeout:
        #         self.get_logger().warn('No amcl_pose received. Using default start position for testing.')
        #         start_pose = self.create_pose(0.0,3.0, 0.9881, 0.1536)
        #         break  # while 루프 탈출
        #     self.get_logger().info('Waiting for current pose...')
        #     rclpy.spin_once(self, timeout_sec=0.5)
        # else:
        #     start_pose = self.current_pose  # 로봇의 현재 위치 저장

        if self.current_pose is None:  
            self.get_logger().warn('Waiting for initial pose...')
            time.sleep(1.0)         # 로봇의 현재 위치 저장

            if self.current_pose is None:
                self.get_logger().warn('No Pose')
                self.current_pose = self.navigator.getPoseStamped([0.0,0.0], TurtleBot4Directions.NORTH)
        
        start_pose = self.current_pose
        self.navigator.info('Calculating best route to retrace steps...')
        best_route, _ = self.find_best_route_brute_force(start_pose, self.visited_spot)     # 최적 경로 계산

        path_names = [self.goal_options[i]['name'] for i in best_route]
        print("\n" + "*"*50)
        print(f"  최적 탐색 경로: {' -> '.join(path_names)}")
        print("*"*50 + "\n")

        # 최적 경로를 따라 주행 시작
        for index in best_route:
            target_name = self.goal_options[index]['name']
            target_pose = self.goal_options[index]['pose']

            gate_name = self.gate_options[self.gate_id]['name']
            gate_pose = self.gate_options[self.gate_id]['pose']

            self.navigator.info(f'Retracing path to {target_name}...')
            self.navigator.startToPose(target_pose)

            while not self.navigator.isTaskComplete():      # 로봇이 이동 중일 때 인지 여부 확인

                # 다른 로봇이 분실물 인지했을 경우, 정지 후 코드 종료
                if self.detected_robot3:
                    self.get_logger().info("robot3 detected")
                    self.navigator.cancelTask()
                    self.stop_robot()    
                    return
                
                # 자신이 분실물 인지했을 경우, 정지 후 접근 및 게이트로 이동
                if self.detected_robot1:
                    self.get_logger().info("robot1 detected")
                    self.navigator.cancelTask()
                    self.stop_robot()       # 추후 접근으로 구현 필요
                    time.sleep(5.0)
                    # 게이트로 이동
                    self.get_logger().info(f'go to {gate_name}')
                    self.navigator.startToPose(gate_pose)

                    while not self.navigator.isTaskComplete():
                        time.sleep(0.1)
                    return
                time.sleep(0.1)

            # 목적지 도달 여부 확인
            result = self.navigator.getResult()
            if result == TaskResult.SUCCEEDED:
                self.navigator.info(f'Checked {target_name} (Visited Spot).')
                time.sleep(1.0)
            elif result == TaskResult.CANCELED:
                self.navigator.info(f'Navigation to {target_name} was canceled.')
            elif result == TaskResult.FAILED:
                self.navigator.error(f'Failed to reach {target_name}.')

        # 탐색 완료했는데도 분실물을 발견하지 못한 경우 DB 업로드 (추후 추가 예정)
        if not self.detected_robot1 and not self.detected_robot3:
            self.navigator.info('DB Upload')

            # /is_found (Bool) 토픽 False로 퍼블리시
            msg_is_found = Bool()
            msg_is_found.data = False
            self.is_found_pub.publish(msg_is_found)

        self.navigator.info('History check completed. Returning to dock...')

def main(args=None):
    rclpy.init(args=args)
    
    tracer = VisitedHistoryPatrol()

    # [핵심 변경] Executor를 생성하고 Node를 추가
    executor = MultiThreadedExecutor()
    executor.add_node(tracer)

    # [핵심 변경] Executor를 별도 쓰레드(Daemon)에서 실행
    # 이렇게 하면 spin()이 백그라운드에서 계속 돌며 콜백(위치 수신, 탐지 등)을 처리합니다.
    executor_thread = threading.Thread(target=executor.spin, daemon=True)
    executor_thread.start()

    try:
        while rclpy.ok():
            # 데이터를 받으면 순찰 시작
            if tracer.search_mode and not tracer.registered: 
                tracer.run_patrol()
                tracer.registered = False 
                tracer.search_mode = False 
                # 탐색이 끝나면 프로그램 종료
                break 
            
    except KeyboardInterrupt:
        pass
    finally:
        tracer.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()