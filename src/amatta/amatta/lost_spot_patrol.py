# robot 3 구동하는 코드: 사용자의 이동 경로를 제외한 주요 구역 탐색
import rclpy
from rclpy.node import Node
import time
import math
import itertools
from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav2_simple_commander.robot_navigator import TaskResult
from std_msgs.msg import Int32MultiArray, Bool
from geometry_msgs.msg import Twist

class LostItemPatrol(Node):
    def __init__(self):
        super().__init__('lost_item_patrol')

        self.navigator = TurtleBot4Navigator()

        # [추가] 토픽 수신 여부와 데이터를 저장할 변수
        self.visited_spot = []              # 사용자의 방문 이력
        self.is_data_received = False       # 데이터 서브스크라이브 여부

        self.subscription = self.create_subscription(
            Int32MultiArray,
            '/visited_spot',
            self.topic_callback,
            10
        )

        self.robot1_pose = None
        self.robot2_pose = None

        self.cmd_vel_pub = self.navigator.create_publisher(
            Twist,
            '/robot3/cmd_vel',  # 또는 '/cmd_vel'
            10)

        self.robot2_sub = self.create_subscription(
            PoseWithCovarianceStamped,
            '/robot3/amcl_pose',
            self.pose_callback,
            10
        )
        self.robot1_sub = self.create_subscription(
            PoseWithCovarianceStamped,
            '/robot1/amcl_pose',  # 로봇 1의 실시간 위치 토픽
            self.robot1_pose_callback,
            10)

        self.detection_sub = self.create_subscription(
            Bool,
            '/is_detected',
            self.detection_callback,
            10)
        

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
    
    def topic_callback(self, msg):
        self.get_logger().info(f"Topic Received! Data: {msg.data}")
        self.visited_spot_raw = list(msg.data)
        self.is_data_received = True

    def robot1_pose_callback(self, msg):
        self.robot1_pose = msg.pose.pose
    
    def detection_callback(self, msg):
        self.is_detected = msg.data

    
    def pose_callback(self, msg):
        # AMCL은 PoseWithCovarianceStamped를 주지만, 
        # 우리가 필요한 건 PoseStamped이므로 변환해서 저장합니다.
        self.current_pose = PoseStamped()
        self.current_pose.header = msg.header
        self.current_pose.pose = msg.pose.pose

        self.robot2_pose = msg.pose.pose
    
    def is_robot1_nearby(self, threshold=1.0):
        """로봇 1이 threshold(미터) 이내에 있는지 확인"""
        if self.robot1_pose is None or self.robot2_pose is None:
            self.get_logger().error(f'로봇 위치 못 받아옴')
            return False

        dist = math.sqrt(
            (self.robot1_pose.position.x - self.robot2_pose.position.x)**2 +
            (self.robot1_pose.position.y - self.robot2_pose.position.y)**2
        )
        self.get_logger().info(f'dist: {dist}, dist<threshold: {dist < threshold}')
        return dist < threshold

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
    
    # def get_offset_pose(self, target_x, target_y, offset_dist=0.1):
    #     """
    #     현재 로봇 위치에서 타겟 위치를 바라보는 방향으로, 
    #     타겟보다 offset_dist 만큼 덜 간 위치를 계산하여 반환
    #     """
    #     # 현재 로봇의 위치 가져오기 (피드백이 없으면 0,0 처리)
    #     feedback = self.navigator.getFeedback()
    #     if feedback:
    #         self.initial_pose = feedback.current_pose
    #     else:
    #         self.get_logger().info('로봇 위치를 못 불러옵니다.')

    def get_distance(self, pose1, pose2):
        x1 = pose1.pose.position.x
        y1 = pose1.pose.position.y
        x2 = pose2.pose.position.x
        y2 = pose2.pose.position.y
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    def find_best_route_brute_force(self, start_pose, spots_indices):
        min_distance = float('inf')
        best_order = []
        
        possible_paths = itertools.permutations(spots_indices)
        
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

    def stop_robot(self):
        """로봇 즉시 정지"""
        stop_msg = Twist()
        stop_msg.linear.x = 0.0
        stop_msg.linear.y = 0.0
        stop_msg.linear.z = 0.0
        stop_msg.angular.x = 0.0
        stop_msg.angular.y = 0.0
        stop_msg.angular.z = 0.0
        
        # 여러 번 publish (확실하게)
        for _ in range(10):
            self.cmd_vel_pub.publish(stop_msg)
            time.sleep(0.01)

    def run_patrol(self):
        # 1. 방문할 장소 결정
        all_indices = list(range(len(self.goal_options)))
        self.visited_spot = [idx for idx in all_indices if idx not in self.visited_spot_raw]
        
        print(f"\n최종 방문할 장소 인덱스: {self.visited_spot}")

        if not self.visited_spot:
            self.navigator.info("No targets selected. Exiting.")
            return

        self.navigator.info('Starting patrol service...')

        if self.current_pose is not None:
            start_pose = self.current_pose
        else:
            self.get_logger().warn('No Pose')

        
        best_route, _ = self.find_best_route_brute_force(start_pose, self.visited_spot)

        path_names = [self.goal_options[i]['name'] for i in best_route]
        self.navigator.info(f'Optimized Route: {path_names}')

        # 3. 주행 시작
        for index in best_route:
            target_name = self.goal_options[index]['name']
            target_pose = self.goal_options[index]['pose']

            while self.is_robot1_nearby(1.5): # 1.5미터 이내면 대기
                self.navigator.info("Robot 1 is too close! Waiting...")
                time.sleep(2.0)

            self.navigator.info(f'Navigating to {target_name}...')
            self.navigator.startToPose(target_pose)

            while not self.navigator.isTaskComplete():
                rclpy.spin_once(self, timeout_sec=0.01)  # 토픽 수신을 위해 한 번만 호출

                if self.is_detected:
                    self.stop_robot()       # 추후 접근으로 구현 필요
                    time.sleep(1.0)

                if self.is_robot1_nearby(2):
                    self.navigator.info("Robot 3 approaching! Yielding...")
                    self.stop_robot()
                    self.navigator.cancelTask()

                    while self.is_robot1_nearby(2):
                        self.navigator.info("Robot 3 approaching! Yielding...")
                        self.stop_robot()
                        time.sleep(1.0)
                    self.navigator.startToPose(target_pose)
                time.sleep(0.1)

            result = self.navigator.getResult()
            if result == TaskResult.SUCCEEDED:
                self.navigator.info(f'Arrived at {target_name}!')
                time.sleep(2.0)
            elif result == TaskResult.CANCELED:
                self.navigator.info(f'Navigation to {target_name} was canceled.')
            elif result == TaskResult.FAILED:
                self.navigator.error(f'Failed to reach {target_name}.')

        self.navigator.info('All tasks completed. Returning to dock...')

def main(args=None):
    rclpy.init(args=args)
    
    patrol_robot = LostItemPatrol()
    
    try:
        # [핵심 수정] 데이터가 들어올 때까지 Node를 Spin(대기) 시킵니다.
        while rclpy.ok():
            rclpy.spin_once(patrol_robot, timeout_sec=0.1)
            
            if patrol_robot.is_data_received:
                # 데이터를 받으면 순찰 시작
                patrol_robot.run_patrol()
                break # 순찰이 끝나면 프로그램 종료 (계속 대기하려면 break 제거 및 플래그 초기화)
                
    except KeyboardInterrupt:
        pass
    finally:
        patrol_robot.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()