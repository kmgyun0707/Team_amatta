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

        # ---------------- 초기화 ----------------
        if not self.navigator.getDockedStatus():
            self.navigator.dock()
        initial_pose = self.navigator.getPoseStamped([0.0, 0.0], TurtleBot4Directions.NORTH)
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
        if msg.detected and not self.detected_self:
            self.get_logger().info("I (Robot 1) FOUND IT! Stopping.")
            self.detected_self = True
            self.navigator.cancelTask()
            self.stop_robot()

    def detection_peer_callback(self, msg):
        if msg.detected and not self.detected_peer:
            self.get_logger().info("Robot 3 FOUND IT! I will stop.")
            self.detected_peer = True
            self.navigator.cancelTask()
            self.stop_robot()

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
        best_route, _ = self.find_best_route_brute_force(start_pose, self.target_indices)
        
        path_names = [self.goal_options[i]['name'] for i in best_route]
        self.get_logger().info(f"Patrol Route: {' -> '.join(path_names)}")

        for index in best_route:
            # 1. 시작 전 종료 조건 확인
            if self.detected_self or self.detected_peer:
                self.reset_state()
                return

            target_name = self.goal_options[index]['name']
            target_pose = self.goal_options[index]['pose']

            self.get_logger().info(f"Moving to {target_name}...")
            self.navigator.goToPose(target_pose)

            # 2. 이동 중 감시 루프
            while not self.navigator.isTaskComplete():
                # [종료 조건] 누군가 찾음
                if self.detected_self or self.detected_peer:
                    self.navigator.cancelTask()
                    self.stop_robot()
                    self.reset_state()
                    return

                # [충돌 방지] Robot 3와 거리 체크
                if self.check_proximity_and_yield():
                    # 양보하느라 멈췄다면, 다시 현재 목표로 이동 명령
                    self.navigator.goToPose(target_pose)
                
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
                if self.detected_self or self.detected_peer: return False # 대기 중 발견 시 탈출
                
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