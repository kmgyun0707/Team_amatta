import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

# TurtleBot4 & Nav2 Imports
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

class VisitedHistoryPatrol(Node):
    def __init__(self):
        super().__init__('visited_history_patrol')
        
        self.callback_group = ReentrantCallbackGroup()
        self.navigator = TurtleBot4Navigator()

        # 상태 변수
        self.search_mode = False            
        self.visited_spots = []             
        self.gate_id = 0
        self.gate_name = ""
        self.gate_pose = None
        
        self.is_patrolling = False          # 현재 순찰 중인지 확인하는 플래그 (중복 실행 방지)
        self.patrol_thread = None           # 순찰 스레드 관리용 변수

        self.detected_robot3 = False
        self.detected_robot1 = False
        self.item_location = None
        
        self.current_pose = None 
        ns = self.get_namespace()

        # QoS
        qos_best_effort = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # ---------------- Subscribers ----------------
        self.search_mode_sub = self.create_subscription(
            Bool, '/search_mode', self.search_mode_callback, 10, callback_group=self.callback_group)
        
        self.subscription = self.create_subscription(
            DbInfo, '/is_registered', self.topic_callback, 10, callback_group=self.callback_group)

        self.subscription_pose = self.create_subscription(
            PoseWithCovarianceStamped, f'{ns}/amcl_pose', self.pose_callback, qos_best_effort, callback_group=self.callback_group)

        self.detection_robot1_sub = self.create_subscription(
            DetectionInfo, '/robot1/is_detected', self.detection_robot1_callback, 10, callback_group=self.callback_group)
        
        self.detection_robot3_sub = self.create_subscription(
            DetectionInfo, '/robot3/is_detected', self.detection_robot3_callback, 10, callback_group=self.callback_group)
        
        # ---------------- Publishers ----------------
        self.pose_pub = self.create_publisher(Pose, '/another_robot_pose', qos_best_effort, callback_group=self.callback_group)
        self.cmd_vel_pub = self.create_publisher(Twist, f'{ns}/cmd_vel', 10, callback_group=self.callback_group)
        self.is_found_pub = self.create_publisher(Bool, f'{ns}/is_found', 10, callback_group=self.callback_group)

        # ---------------- 좌표 데이터 ----------------
        self.goal_options = [
            {'name': 'Entrance', 'pose': self.create_pose(-3.26, 3.77, 0.9881, 0.1536)},
            {'name': 'Bank', 'pose': self.create_pose(-2.08, 3.45, 0.4327, 0.9015)},
            {'name': 'Counter', 'pose': self.create_pose(-0.584, 3.64, -0.7689, 0.6394)},
            {'name': 'Bench_1', 'pose': self.create_pose(-0.791, 2.19, -0.7689, 0.6394)},
            {'name': 'Bench_2', 'pose': self.create_pose(-0.672, 0.615, 0.58, 0.8146)},
            {'name': 'Ladies_Room', 'pose': self.create_pose(-0.547, -0.636, -0.1166, 0.9931)},
            {'name': 'Duty_Free', 'pose': self.create_pose(-2.35, 0.799, 0.7177, 0.6963)},
            {'name': 'Mens_Room', 'pose': self.create_pose(-3.16, 2.58, 0.7177, 0.6963)}
        ]
        self.gate_options = [
            {'name': 'Gate_1', 'pose': self.create_pose(-0.76, -1.59, 0.9881, 0.1536)},
            {'name': 'Gate_2', 'pose': self.create_pose(-2.18, -1.26, -0.7512, 0.66)},
        ]

        # ---------------- 초기화 ----------------
        # if not self.navigator.getDockedStatus():
        #      self.navigator.dock()
        # initial_pose = self.navigator.getPoseStamped([0.0, 0.0], TurtleBot4Directions.NORTH)
        # self.navigator.setInitialPose(initial_pose)
        # self.navigator.waitUntilNav2Active()
        # self.navigator.undock()
        # self.get_logger().info("Robot 3 Ready.")


    # ---------------- Callbacks ----------------

    def search_mode_callback(self, msg):
        self.search_mode = msg.data
        if self.search_mode:
            self.get_logger().info("Search Mode: ON")
            # 모드가 켜질 때 조건 확인
            self.check_and_start_patrol()
        else:
            self.get_logger().info("Search Mode: OFF")

    def topic_callback(self, msg):
        self.visited_spots = list(msg.visited_spots)
        
        # 게이트 ID 처리
        raw_gate_id = msg.gate_id
        if raw_gate_id >= 8:
            self.gate_id = raw_gate_id - 8
        else:
            self.gate_id = 0

        if 0 <= self.gate_id < len(self.gate_options):
            self.gate_name = self.gate_options[self.gate_id]['name']
            self.gate_pose = self.gate_options[self.gate_id]['pose']
        
        self.get_logger().info(f"Received Path: {self.visited_spots}")
        
        # 경로 데이터가 들어왔을 때 조건 확인
        self.check_and_start_patrol()

    def pose_callback(self, msg):
        p = PoseStamped()
        p.header = msg.header
        p.pose = msg.pose.pose
        self.current_pose = p

    def detection_robot1_callback(self, msg):
        # [수정] 감지되어도 무시하도록 변경
        if msg.detected:
             return
        
        # if msg.detected and not self.detected_robot1:
        #     self.get_logger().info("ROBOT 1 DETECTED ITEM!")
        #     self.detected_robot1 = True
        #     self.item_location = msg.goal 
        #     self.navigator.cancelTask()
        #     self.stop_robot()

    def detection_robot3_callback(self, msg):
        # [수정] 감지되어도 무시하도록 변경
        if msg.detected:
             return

        # if msg.detected and not self.detected_robot3:
        #     self.get_logger().info("ROBOT 3 DETECTED ITEM!")
        #     self.detected_robot3 = True

        #     self.item_location = msg.goal

        #     self.navigator.cancelTask()
        #     self.stop_robot()

        #     # 접근 (이제 self.item_location이 None이 아니므로 에러가 나지 않습니다)
        #     if self.item_location is not None:
        #         approach_pose = self.get_offset_pose(self.item_location, 0.6)
        #         self.navigator.startToPose(approach_pose)
        #         while not self.navigator.isTaskComplete(): time.sleep(0.1)
                
        #         # 대기
        #         self.get_logger().info("Waiting for load...")
        #         time.sleep(7.0)
                
        #         # 게이트 이동
        #         if self.gate_pose:
        #             self.get_logger().info(f"Going to Gate...")
        #             self.navigator.startToPose(self.gate_pose)
        #             while not self.navigator.isTaskComplete(): time.sleep(0.1)
        #     else:
        #         self.get_logger().error("Detected item but location is None")

    # ---------------- Control Logic ----------------

    def check_and_start_patrol(self):
        """
        콜백에서 호출되는 함수. 조건이 맞으면 '스레드'를 생성하여 순찰을 보냄.
        """
        # 1. 이미 순찰 중이면 무시
        if self.is_patrolling:
            return

        # 2. 탐색 모드 ON + 방문 장소 데이터 있음
        if self.search_mode and len(self.visited_spots) > 0:
            self.get_logger().info("Condition Met! Starting Patrol Thread...")
            self.is_patrolling = True
            
            # [중요] run_patrol을 별도 스레드로 실행 (콜백 블로킹 방지)
            self.patrol_thread = threading.Thread(target=self.run_patrol)
            self.patrol_thread.start()

    def run_patrol(self):
        """
        실제 로봇을 움직이는 긴 작업 (별도 스레드에서 실행됨)
        """
        self.get_logger().info("Patrol Thread Started.")
        
        # 위치 초기화 대기
        if self.current_pose is None:
            time.sleep(1.0)
            if self.current_pose is None:
                self.get_logger().warn("No Pose detected. Aborting.")
                self.reset_state()
                return

        # 최단 경로 계산
        start_pose = self.current_pose
        
        # [수정] Nav2 기반 경로 계산 사용
        # best_route, _ = self.find_best_route_brute_force(start_pose, self.visited_spots)
        best_route, _ = self.find_best_route_using_nav2(start_pose, self.visited_spots)
        
        # 이동 루프
        for index in best_route:
            # [수정] 감지되어도 무시하므로 주석 처리
            # # 이동 전 감지 확인
            # if self.detected_robot1:
            #     self.handle_retrieval_sequence()
            #     self.reset_state()
            #     return
            # if self.detected_robot3:
            #     self.reset_state()
            #     return

            target_pose = self.goal_options[index]['pose']
            self.navigator.startToPose(target_pose)

            # 이동 중 감시 루프
            while not self.navigator.isTaskComplete():
                # [수정] 감지되어도 무시하므로 주석 처리
                # if self.detected_robot1:
                #     self.navigator.cancelTask()
                #     self.stop_robot()
                #     # self.handle_retrieval_sequence()
                #     self.reset_state()
                #     return
                # if self.detected_robot3:
                #     self.navigator.cancelTask()
                #     self.stop_robot()
                #     self.handle_retrieval_sequence()
                #     self.reset_state()
                #     return
                time.sleep(0.1)

            # 도착 확인
            result = self.navigator.getResult()
            if result == TaskResult.SUCCEEDED:
                self.get_logger().info(f"Checked spot {index}.")
                time.sleep(0.5)

        # 모든 경로 탐색 종료 (못 찾음)
        if not self.detected_robot1 and not self.detected_robot3:
            self.get_logger().info("Patrol Finished. Item NOT found.")
            msg = Bool()
            msg.data = False
            self.is_found_pub.publish(msg)
        
        # 종료 처리
        self.reset_state()

    def reset_state(self):
        """순찰 종료 후 상태 초기화"""
        self.is_patrolling = False
        self.search_mode = False 
        self.visited_spots = [] 
        self.detected_robot1 = False
        self.detected_robot3 = False
        self.get_logger().info("State Reset. Waiting for new commands...")

    # --- Helper Functions (동일) ---
    def create_pose(self, x, y, z_orient, w_orient):
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.navigator.get_clock().now().to_msg()
        pose.pose.position.x = float(x)
        pose.pose.position.y = float(y)
        pose.pose.orientation.z = float(z_orient)
        pose.pose.orientation.w = float(w_orient)
        return pose
    
    # [수정] Nav2 getPath를 이용한 경로 길이 계산 헬퍼 함수 추가
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

    # [수정] getPath를 사용하여 순열 중 최단 경로를 찾는 함수 추가
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
        valid_indices = [i for i in spots_indices if i < len(self.goal_options)]
        if not valid_indices: return [], 0.0
        
        # pose 객체만 미리 추출하여 계산 속도 향상
        options_poses = {i: self.goal_options[i]['pose'] for i in valid_indices}

        for path in itertools.permutations(valid_indices):
            current_dist = 0.0
            curr = start_pose
            for idx in path:
                tgt = options_poses[idx]
                # 거리 계산
                dx = tgt.pose.position.x - curr.pose.position.x
                dy = tgt.pose.position.y - curr.pose.position.y
                current_dist += math.sqrt(dx*dx + dy*dy)
                curr = tgt
            
            if current_dist < min_distance:
                min_distance = current_dist
                best_order = list(path)
        return best_order, min_distance

    def get_offset_pose(self, target_pose, offset_dist=0.6):
        if not self.current_pose: return target_pose
        rx, ry = self.current_pose.pose.position.x, self.current_pose.pose.position.y
        tx, ty = target_pose.pose.position.x, target_pose.pose.position.y
        theta = math.atan2(ty - ry, tx - rx)
        return self.create_pose(tx - offset_dist*math.cos(theta), ty - offset_dist*math.sin(theta), 0.0, 1.0)

    def stop_robot(self):
        stop_msg = Twist()
        for _ in range(5):
            self.cmd_vel_pub.publish(stop_msg)
            time.sleep(0.05)

    def handle_retrieval_sequence(self):
        if not self.item_location: return
        self.get_logger().info("Retrieving Item...")
        
        # 접근
        approach_pose = self.get_offset_pose(self.item_location, 0.6)
        self.navigator.startToPose(approach_pose)
        while not self.navigator.isTaskComplete(): time.sleep(0.1)
        
        # 대기
        self.get_logger().info("Waiting for load...")
        time.sleep(7.0)
        
        # 게이트 이동
        if self.gate_pose:
            self.get_logger().info(f"Going to Gate...")
            self.navigator.startToPose(self.gate_pose)
            while not self.navigator.isTaskComplete(): time.sleep(0.1)

def main(args=None):
    rclpy.init(args=args)
    tracer = VisitedHistoryPatrol()
    
    # Executor 설정
    executor = MultiThreadedExecutor()
    executor.add_node(tracer)

    try:
        # 이제 main은 오직 spin만 담당!
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        tracer.stop_robot()
        tracer.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()