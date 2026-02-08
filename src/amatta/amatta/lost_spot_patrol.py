import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

# TurtleBot4 & Nav2
from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator
from nav2_simple_commander.robot_navigator import TaskResult

# Messages
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped, Twist, Pose
from std_msgs.msg import Bool
from airport_guide_interfaces.msg import DbInfo, DetectionInfo

import time
import math
import itertools
import threading

class LostItemPatrol(Node):
    def __init__(self):
        super().__init__('lost_item_patrol')
        
        self.callback_group = ReentrantCallbackGroup()
        self.navigator = TurtleBot4Navigator()

        # 상태 변수
        self.search_mode = False
        self.is_patrolling = False          # 스레드 중복 실행 방지
        self.patrol_thread = None
        self.gate_id = None              # 게이트 ID
        self.gate_pose = None             # 게이트 좌표
        
        self.visited_indices = []           # 사용자가 방문한 곳 (제외할 곳)
        self.target_indices = []            # 실제 탐색할 곳 (전체 - 방문한 곳)
        
        self.detected_self = False          # 내가(Robot 1) 발견했는지
        self.detected_peer = False          # 동료(Robot 3)가 발견했는지
        
        self.current_pose = None            # 내 위치
        self.peer_pose = None               # 동료 로봇 위치 (Robot 3)

        ns = self.get_namespace()           # e.g., /robot1

        # QoS 설정
        qos_best_effort = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # ---------------- Subscribers ----------------
        # 1. 탐색 모드
        self.search_mode_sub = self.create_subscription(
            Bool, '/search_mode', self.search_mode_callback, 10, callback_group=self.callback_group)

        # 2. DB 정보 (방문 기록)
        self.subscription = self.create_subscription(
            DbInfo, '/is_registered', self.db_callback, 10, callback_group=self.callback_group)

        # 3. 내 위치 (AMCL)
        self.subscription_pose = self.create_subscription(
            PoseWithCovarianceStamped, f'{ns}/amcl_pose', self.pose_callback, qos_best_effort, callback_group=self.callback_group)
        
        # 4. 동료 로봇 위치 (Robot 3가 발행하는 토픽 구독)
        self.peer_pose_sub = self.create_subscription(
            Pose, '/another_robot_pose', self.peer_pose_callback, qos_best_effort, callback_group=self.callback_group)

        # 5. 감지 신호 (Robot 1 - 자신)
        self.detection_self_sub = self.create_subscription(
            DetectionInfo, '/robot1/is_detected', self.detection_self_callback, 10, callback_group=self.callback_group)
        
        # 6. 감지 신호 (Robot 3 - 동료)
        self.detection_peer_sub = self.create_subscription(
            DetectionInfo, '/robot3/is_detected', self.detection_peer_callback, 10, callback_group=self.callback_group)
        
        # ---------------- Publishers ----------------
        self.cmd_vel_pub = self.create_publisher(Twist, f'{ns}/cmd_vel', 10, callback_group=self.callback_group)
        self.is_found_pub = self.create_publisher(Bool, f'{ns}/is_found', 10, callback_group=self.callback_group)

        # ---------------- 좌표 데이터 (Robot 1 기준) ----------------
        self.goal_options = [
            {'name': 'Entrance', 'pose': self.create_pose(-3.26, 3.71, 0.9881, 0.1536)},
            {'name': 'Bank', 'pose': self.create_pose(-2.39, 3.15, 0.4327, 0.9015)},
            {'name': 'Counter', 'pose': self.create_pose(-0.54, 3.64, 0.7177, 0.6963)},
            {'name': 'Bench_1', 'pose': self.create_pose(-0.54, 2.12, -0.7689, 0.6394)},
            {'name': 'Bench_2', 'pose': self.create_pose(-0.83, 0.80, 0.58, 0.8146)},
            {'name': 'Ladies_Room', 'pose': self.create_pose(-0.486, -0.75, -0.1166, 0.9931)},
            {'name': 'Duty_Free', 'pose': self.create_pose(-1.99, 0.82, -0.9927, 0.1203)},
            {'name': 'Mens_Room', 'pose': self.create_pose(-3.29, 2.6, 0.9980, 0.0631)}
        ]

        self.gate_options = [
            {'name': 'Gate_1', 'pose': self.create_pose(-0.60, -1.31, -0.6276, 0.7785)},
            {'name': 'Gate_2', 'pose': self.create_pose(-2.13, -1.37, -0.7512, 0.66)},
        ]
        

        # ---------------- 초기화 ----------------
        if not self.navigator.getDockedStatus():
            self.navigator.dock()
        initial_pose = self.navigator.getPoseStamped([0.0, 3.0], TurtleBot4Directions.NORTH)
        self.navigator.setInitialPose(initial_pose)
        self.navigator.waitUntilNav2Active()
        self.navigator.undock()
        self.get_logger().info("Robot 1 Initialized.")

    # ---------------- Callbacks ----------------
    
    def search_mode_callback(self, msg):
        self.search_mode = msg.data
        if self.search_mode:
            self.get_logger().info("Search Mode: ON")
            self.check_and_start_patrol()
        else:
            self.get_logger().info("Search Mode: OFF")

    def db_callback(self, msg):
        self.gate_id = msg.gate_id - 8
        self.gate_pose = self.gate_options[self.gate_id]['pose']
        self.visited_indices = list(msg.visited_spots)
        self.get_logger().info(f"DB Info Received. Visited: {self.visited_indices}")
        
        # [핵심 로직] 전체 장소 중 '방문 안 한 곳'만 필터링
        all_indices = set(range(len(self.goal_options)))
        visited_set = set(self.visited_indices)
        
        # 차집합 연산 (전체 - 방문한 곳)
        self.target_indices = list(all_indices - visited_set)
        self.get_logger().info(f"Target Spots to Patrol: {self.target_indices}")

        self.check_and_start_patrol()

    def pose_callback(self, msg):
        p = PoseStamped()
        p.header = msg.header
        p.pose = msg.pose.pose
        self.current_pose = p

    def peer_pose_callback(self, msg):
        """상대방(Robot 3)의 위치 수신"""
        self.peer_pose = msg # geometry_msgs/Pose

    def detection_self_callback(self, msg):
        # # [수정] 감지되어도 아무 동작 안 하고 무시하도록 변경 (경로 생성 알고리즘 검증용, 추후 제거 필요)
        if msg.detected:
            # self.get_logger().info(f"Robot 1 DETECTED something, but IGNORING it to continue path.")
            return
        
        # 아래 로직들 모두 주석 처리하여 실행되지 않게 함
        # self.goal_x = msg.goal.pose.position.x
        # self.goal_y = msg.goal.pose.position.y

        # # self.offset_goal_pose = self.get_offset_pose(self.goal_x, self.goal_y, offset_dist=0.6) # offset_dist 튜닝 필요: dist 절반 시도해보기

        # temp_target_pose = self.create_pose(self.goal_x, self.goal_y, 0.0, 1.0)
        # self.offset_goal_pose = self.get_offset_pose(temp_target_pose, offset_dist=0.6)

        # if msg.detected and not self.detected_self:
        #     self.get_logger().info("I (Robot 1) FOUND IT! Stopping.")
        #     self.detected_self = True
        #     self.navigator.cancelTask()
        #     self.stop_robot()

        #     # 분실물에 접근
        #     self.get_logger().info(f'close to stuff')
        #     self.navigator.startToPose(self.offset_goal_pose)
        #     while not self.navigator.isTaskComplete():
        #         time.sleep(0.1)
            
        #     # 분실물 수거 기다리기
        #     self.get_logger().info(f'please put your lost item on robot3 head')
        #     time.sleep(5.0)  
            
        #     # 게이트로 이동
        #     self.navigator.startToPose(self.gate_pose)
        #     while not self.navigator.isTaskComplete():
        #         time.sleep(0.1)

    def detection_peer_callback(self, msg):
        # [수정] 동료 로봇이 감지해도 아무 동작 안 하고 무시하도록 변경
        if msg.detected:
            #  self.get_logger().info(f"Robot 3 detected something, but Robot 1 is IGNORING it.")
             return
        
        # if msg.detected and not self.detected_peer:
        #     self.get_logger().info("Robot 3 FOUND IT! I will stop.")
        #     self.detected_peer = True
        #     self.navigator.cancelTask()
        #     self.stop_robot()
    
    # 수정된 get_offset_pose
    def get_offset_pose(self, target_pose, offset_dist=0.6):
        if not self.current_pose: return target_pose
        rx, ry = self.current_pose.pose.position.x, self.current_pose.pose.position.y
        tx, ty = target_pose.pose.position.x, target_pose.pose.position.y
        theta = math.atan2(ty - ry, tx - rx)
        return self.create_pose(tx - offset_dist*math.cos(theta), ty - offset_dist*math.sin(theta), 0.0, 1.0)

    
    # ---------------- Control Logic ----------------

    def check_and_start_patrol(self):
        """탐색 시작 조건 확인 및 스레드 생성"""
        if self.is_patrolling:
            return

        # 조건: 탐색모드 ON + 탐색할 타겟(안 가본 곳)이 정해짐
        if self.search_mode and len(self.target_indices) > 0:
            self.get_logger().info("Conditions Met. Spawning Patrol Thread...")
            self.is_patrolling = True
            self.patrol_thread = threading.Thread(target=self.run_patrol)
            self.patrol_thread.start()

    def run_patrol(self):
        """실제 순찰 로직 (별도 스레드)"""
        self.get_logger().info("Patrol Thread Started.")

        if self.current_pose is None:
            time.sleep(1.0)
            if self.current_pose is None:
                self.get_logger().error("No Pose. Aborting.")
                self.reset_state()
                return

        # 최단 경로 계산 (TSP)
        start_pose = self.current_pose

        # --- 측정 시작: Brute Force (유클리드) ---
        t0 = time.time()
        route_bf, dist_bf = self.find_best_route_brute_force(start_pose, self.target_indices)
        t1 = time.time()
        time_bf = t1 - t0

        # --- 측정 시작: Nav2 (실제 경로) ---
        t2 = time.time()
        route_nav, dist_nav = self.find_best_route_using_nav2(start_pose, self.target_indices)
        t3 = time.time()
        time_nav = t3 - t2
        
        # --- [데이터 출력] 비교 로그 ---
        self.get_logger().info(f"📊 [알고리즘 비교 결과]")
        self.get_logger().info(f"1. 연산 시간: BruteForce={time_bf:.4f}s vs Nav2={time_nav:.4f}s")
        self.get_logger().info(f"2. 예측 거리: BruteForce={dist_bf:.2f}m vs Nav2={dist_nav:.2f}m")
        self.get_logger().info(f"3. 경로 순서 다름 여부: {'다름!' if route_bf != route_nav else '같음'}")


        # best_route, _ = self.find_best_route_brute_force(start_pose, self.target_indices)
        best_route = route_nav
        
        path_names = [self.goal_options[i]['name'] for i in best_route]
        self.get_logger().info(f"Patrol Route: {' -> '.join(path_names)}")

        for index in best_route:
            # -> [수정] 감지되어도 무시하므로 주석 처리
            # # 1. 시작 전 종료 조건 확인
            # if self.detected_self or self.detected_peer:
            #     self.reset_state()
            #     return

            target_name = self.goal_options[index]['name']
            target_pose = self.goal_options[index]['pose']

            self.get_logger().info(f"Moving to {target_name}...")
            self.navigator.startToPose(target_pose)

            # 2. 이동 중 감시 루프
            while not self.navigator.isTaskComplete():
                # [수정] 종료 조건(감지 시 정지) 삭제 -> 무조건 완주
                # # [종료 조건] 누군가 찾음
                # if self.detected_self or self.detected_peer:
                #     self.navigator.cancelTask()
                #     self.stop_robot()
                #     self.reset_state()
                #     return

                # [충돌 방지] Robot 3와 거리 체크
                if self.check_proximity_and_yield():
                    # 양보하느라 멈췄다면, 다시 현재 목표로 이동 명령
                    self.navigator.startToPose(target_pose)
                
                time.sleep(0.1)

            # 3. 도착 결과 처리
            result = self.navigator.getResult()
            if result == TaskResult.SUCCEEDED:
                self.get_logger().info(f"Checked {target_name}.")
                time.sleep(1.0) # 잠시 탐색

        # 모든 곳을 다 돌았는데 못 찾음
        if not self.detected_self and not self.detected_peer:
            self.get_logger().info("Patrol Finished. Item NOT found by Robot 1.")
            # Robot 3가 처리할 수도 있으므로 여기서는 False만 발행하거나 생략 가능
            # msg = Bool()
            # msg.data = False
            # self.is_found_pub.publish(msg)

        self.reset_state()

    def check_proximity_and_yield(self, safe_dist=1.5):
        """
        Robot 3가 가까이 있으면 멈추고 기다림.
        Return: True if yielded (paused), False otherwise
        """
        if self.peer_pose is None or self.current_pose is None:
            return False

        # 거리 계산
        dx = self.current_pose.pose.position.x - self.peer_pose.position.x
        dy = self.current_pose.pose.position.y - self.peer_pose.position.y
        dist = math.sqrt(dx*dx + dy*dy)

        # 안전 거리 침범 시
        if dist < safe_dist:
            self.get_logger().warn(f"Collision Warning! Distance: {dist:.2f}m. Yielding...")
            self.navigator.cancelTask()
            self.stop_robot()

            # 멀어질 때까지 대기
            while dist < safe_dist:
                # [수정] 대기 중 발견해도 탈출 안함 (계속 대기하다가 길 비키면 이동)
                # if self.detected_self or self.detected_peer: return False # 대기 중 발견 시 탈출
                
                # 위치 업데이트 후 다시 계산
                if self.peer_pose and self.current_pose:
                    dx = self.current_pose.pose.position.x - self.peer_pose.position.x
                    dy = self.current_pose.pose.position.y - self.peer_pose.position.y
                    dist = math.sqrt(dx*dx + dy*dy)
                
                time.sleep(0.5)
            
            self.get_logger().info("Path Clear. Resuming...")
            return True # 양보 했음
        
        return False # 양보 안 함 (안전함)

    def reset_state(self):
        """순찰 종료 후 상태 초기화"""
        self.is_patrolling = False
        self.search_mode = False 
        self.visited_indices = []
        self.target_indices = []
        self.detected_self = False
        self.detected_peer = False
        self.get_logger().info("State Reset.")

    # ---------------- Helper Functions ----------------
    def create_pose(self, x, y, z_orient, w_orient):
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.navigator.get_clock().now().to_msg()
        pose.pose.position.x = float(x)
        pose.pose.position.y = float(y)
        pose.pose.orientation.z = float(z_orient)
        pose.pose.orientation.w = float(w_orient)
        return pose

    # [수정] Nav2 getPath를 이용한 경로 길이 계산 헬퍼 함수
    def calculate_nav_path_length(self, start, end):
        """
        Navigator의 getPath를 호출하여 실제 경로(Path)를 받아오고,
        그 경로의 총 길이를 계산하여 반환합니다.
        """
        # 경로 생성 요청 (Plan)
        path = self.navigator.getPath(start, end)
        
        if path is None or len(path.poses) < 2:
            return float('inf')  # 경로 생성 실패 시 무한대 거리 반환

        total_dist = 0.0
        # 생성된 경로의 점들을 순회하며 거리 누적
        for i in range(len(path.poses) - 1):
            p1 = path.poses[i].pose.position
            p2 = path.poses[i+1].pose.position
            dist = math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)
            total_dist += dist
            
        return total_dist

    # [수정] getPath를 사용하여 순열 중 최단 경로를 찾는 함수
    def find_best_route_using_nav2(self, start_pose, spots_indices):
        """
        가능한 모든 순서(Permutations)에 대해 Nav2 getPath로 실제 주행 거리를 계산하고,
        가장 짧은 이동 거리를 가지는 순서를 반환합니다.
        """
        min_total_distance = float('inf')
        best_order = []
        
        # 인덱스 유효성 검사
        valid_indices = [i for i in spots_indices if i < len(self.goal_options)]
        if not valid_indices: return [], 0.0

        options_poses = {i: self.goal_options[i]['pose'] for i in valid_indices}
        
        self.get_logger().info("Calculating optimal path using Nav2 getPath... (This might take a moment)")

        # 모든 방문 순서 조합에 대해
        for path in itertools.permutations(valid_indices):
            current_total_dist = 0.0
            curr_pose = start_pose
            valid_path = True
            
            for idx in path:
                target_pose = options_poses[idx]
                
                # Nav2 Plan 계산 호출
                dist_segment = self.calculate_nav_path_length(curr_pose, target_pose)
                
                # 경로 생성 실패 시 이 조합은 버림
                if dist_segment == float('inf'):
                    valid_path = False
                    break
                    
                current_total_dist += dist_segment
                curr_pose = target_pose # 다음 구간의 시작점은 현재 구간의 도착점
            
            if valid_path and current_total_dist < min_total_distance:
                min_total_distance = current_total_dist
                best_order = list(path)
        
        self.get_logger().info(f"Optimal Path Found! Total Distance: {min_total_distance:.2f}m")
        return best_order, min_total_distance

    def find_best_route_brute_force(self, start_pose, spots_indices):
        min_distance = float('inf')
        best_order = []
        
        # 인덱스 유효성 검사
        valid_indices = [i for i in spots_indices if i < len(self.goal_options)]
        if not valid_indices: return [], 0.0

        options_poses = {i: self.goal_options[i]['pose'] for i in valid_indices}

        for path in itertools.permutations(valid_indices):
            current_dist = 0.0
            curr = start_pose
            for idx in path:
                tgt = options_poses[idx]
                dx = tgt.pose.position.x - curr.pose.position.x
                dy = tgt.pose.position.y - curr.pose.position.y
                current_dist += math.sqrt(dx*dx + dy*dy)
                curr = tgt
            
            if current_dist < min_distance:
                min_distance = current_dist
                best_order = list(path)
        return best_order, min_distance

    def stop_robot(self):
        stop_msg = Twist()
        for _ in range(5):
            self.cmd_vel_pub.publish(stop_msg)
            time.sleep(0.05)

def main(args=None):
    rclpy.init(args=args)
    patrol_robot = LostItemPatrol()
    
    executor = MultiThreadedExecutor()
    executor.add_node(patrol_robot)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        patrol_robot.stop_robot()
        patrol_robot.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()