import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import rclpy.logging 

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

        # Nav2 네비게이터의 불필요한 "Getting path..." 로그 숨기기 (INFO -> WARN)
        self.navigator.get_logger().set_level(rclpy.logging.LoggingSeverity.WARN)

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

    # ---------------- Callbacks ----------------

    def search_mode_callback(self, msg):
        self.search_mode = msg.data
        if self.search_mode:
            self.get_logger().info("Search Mode: ON")
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
        self.check_and_start_patrol()

    def pose_callback(self, msg):
        p = PoseStamped()
        p.header = msg.header
        p.pose = msg.pose.pose
        self.current_pose = p

    def detection_robot1_callback(self, msg):
        if msg.detected: return

    def detection_robot3_callback(self, msg):
        if msg.detected: return

    # ---------------- Control Logic ----------------

    def check_and_start_patrol(self):
        if self.is_patrolling:
            return

        if self.search_mode and len(self.visited_spots) > 0:
            self.get_logger().info("Condition Met! Starting Patrol Thread...")
            self.is_patrolling = True
            self.patrol_thread = threading.Thread(target=self.run_patrol)
            self.patrol_thread.start()

    def run_patrol(self):
        self.get_logger().info("Patrol Thread Started.")
        
        # [수정] 위치 초기화 대기 루프 (최대 5초 대기)
        for _ in range(10):
            if self.current_pose is not None:
                break
            self.get_logger().warn("Waiting for AMCL pose...")
            time.sleep(0.5)

        if self.current_pose is None:
            self.get_logger().error("No Pose detected after 5 seconds. Aborting.")
            self.reset_state()
            return

        start_pose = self.current_pose

        # ================= [성능 비교 측정 구간 시작] =================
        self.get_logger().info("--- 📊 Algorithm Performance Comparison Start ---")

        # 1. Brute Force (유클리드 직선 거리) 측정
        t0 = time.time()
        route_bf, dist_bf = self.find_best_route_brute_force(start_pose, self.visited_spots)
        t1 = time.time()
        time_bf = t1 - t0

        # 2. Nav2 Path (실제 주행 경로) 측정
        t2 = time.time()
        route_nav, dist_nav = self.find_best_route_using_nav2(start_pose, self.visited_spots)
        t3 = time.time()
        time_nav = t3 - t2

        # 3. 결과 비교 로그 출력
        self.get_logger().info(f"1. [Computation Time] BruteForce: {time_bf:.4f}s  vs  Nav2: {time_nav:.4f}s")
        self.get_logger().info(f"2. [Total Distance]   BruteForce: {dist_bf:.2f}m    vs  Nav2: {dist_nav:.2f}m")
        
        if route_bf == route_nav:
            self.get_logger().info(f"3. [Route Result]     SAME Order: {route_nav}")
        else:
            self.get_logger().warn(f"3. [Route Result]     DIFFERENT Order!")
            self.get_logger().warn(f"   - BruteForce Suggestion: {route_bf}")
            self.get_logger().warn(f"   - Nav2 (Real) Suggestion: {route_nav}")
        
        self.get_logger().info("--- 📊 Comparison End ---")
        # ================= [성능 비교 측정 구간 끝] =================
        
        # [최적화] 위에서 계산한 Nav2 결과(route_nav)를 재사용
        best_route = route_nav
        
        # 만약 Nav2 경로 계산이 모두 실패했다면, 차선책으로 Brute Force 사용
        if not best_route:
             self.get_logger().warn("Nav2 Path planning failed. Falling back to Brute Force.")
             best_route = route_bf

        self.get_logger().info(f"Final Patrol Route: {best_route}")

        # 이동 루프
        for index in best_route:
            target_pose = self.goal_options[index]['pose']
            self.navigator.startToPose(target_pose)

            while not self.navigator.isTaskComplete():
                time.sleep(0.1)

            result = self.navigator.getResult()
            if result == TaskResult.SUCCEEDED:
                self.get_logger().info(f"Checked spot {index}.")
                time.sleep(0.5)

        if not self.detected_robot1 and not self.detected_robot3:
            self.get_logger().info("Patrol Finished. Item NOT found.")
            msg = Bool()
            msg.data = False
            self.is_found_pub.publish(msg)
        
        self.reset_state()

    def reset_state(self):
        self.is_patrolling = False
        self.search_mode = False 
        self.visited_spots = [] 
        self.detected_robot1 = False
        self.detected_robot3 = False
        self.get_logger().info("State Reset. Waiting for new commands...")

    # --- Helper Functions ---
    def create_pose(self, x, y, z_orient, w_orient):
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.navigator.get_clock().now().to_msg()
        pose.pose.position.x = float(x)
        pose.pose.position.y = float(y)
        pose.pose.orientation.z = float(z_orient)
        pose.pose.orientation.w = float(w_orient)
        return pose
    
    def calculate_nav_path_length(self, start, end):
        """
        Navigator의 getPath를 호출하여 실제 경로 길이를 계산.
        잦은 호출로 인한 에러를 방지하기 위해 딜레이와 예외 처리를 추가함.
        """
        try:
            time.sleep(0.1)
            path = self.navigator.getPath(start, end)
            
            if path is None or len(path.poses) < 2:
                return float('inf')

            total_dist = 0.0
            for i in range(len(path.poses) - 1):
                p1 = path.poses[i].pose.position
                p2 = path.poses[i+1].pose.position
                dist = math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)
                total_dist += dist
                
            return total_dist

        except Exception as e:
            self.get_logger().warn(f"Path planning failed (ignored): {e}")
            return float('inf')

    def find_best_route_using_nav2(self, start_pose, spots_indices):
        min_total_distance = float('inf')
        best_order = []
        
        valid_indices = [i for i in spots_indices if i < len(self.goal_options)]
        if not valid_indices: return [], 0.0

        options_poses = {i: self.goal_options[i]['pose'] for i in valid_indices}
        
        self.get_logger().info("Calculating optimal path using Nav2 getPath... (This might take a moment)")

        for path in itertools.permutations(valid_indices):
            current_total_dist = 0.0
            curr_pose = start_pose
            valid_path = True
            
            for idx in path:
                target_pose = options_poses[idx]
                dist_segment = self.calculate_nav_path_length(curr_pose, target_pose)
                
                if dist_segment == float('inf'):
                    valid_path = False
                    break
                    
                current_total_dist += dist_segment
                curr_pose = target_pose
            
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
        
        approach_pose = self.get_offset_pose(self.item_location, 0.6)
        self.navigator.startToPose(approach_pose)
        while not self.navigator.isTaskComplete(): time.sleep(0.1)
        
        self.get_logger().info("Waiting for load...")
        time.sleep(7.0)
        
        if self.gate_pose:
            self.get_logger().info(f"Going to Gate...")
            self.navigator.startToPose(self.gate_pose)
            while not self.navigator.isTaskComplete(): time.sleep(0.1)

def main(args=None):
    rclpy.init(args=args)
    tracer = VisitedHistoryPatrol()
    
    executor = MultiThreadedExecutor()
    executor.add_node(tracer)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        tracer.stop_robot()
        tracer.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()