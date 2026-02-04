import rclpy
import time
import math
import itertools
from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import TaskResult

class VisitedHistoryPatrol:
    """
    사용자가 방문했던 장소들(History)을 입력받아,
    최단 거리로 해당 장소들을 순찰(Retrace)하는 클래스
    """
    def __init__(self):
        self.navigator = TurtleBot4Navigator()

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

        # 4. 목표 지점(장소 DB) 정의
        self.goal_options = [
            {'name': 'Gate_1',    'pose': self.create_pose(-0.76, -1.59, 0.9881, 0.1536)},
            {'name': 'Duty_Free', 'pose': self.create_pose(-2.35, 0.799, 0.7177, 0.6963)},
            {'name': 'Mens_Room', 'pose': self.create_pose(-3.23, 2.73, 0.7177, 0.6963)},
            {'name': 'Counter',   'pose': self.create_pose(-0.584, 3.64, -0.7689, 0.6394)}
        ]

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

    def get_distance(self, pose1, pose2):
        x1 = pose1.pose.position.x
        y1 = pose1.pose.position.y
        x2 = pose2.pose.position.x
        y2 = pose2.pose.position.y
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    def find_best_route_brute_force(self, start_pose, spots_indices):
        """방문했던 장소들을 가장 효율적으로 도는 순서를 계산"""
        min_distance = float('inf')
        best_order = []
        
        # 순열 생성 (모든 방문 순서 고려)
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

    def get_user_history(self):
        """사용자로부터 방문했던 장소(이력)를 입력받음"""
        print("\n" + "="*40)
        print("      [ 장소 목록 (Location DB) ]")
        for i, option in enumerate(self.goal_options):
            print(f"  {i} : {option['name']}")
        print("="*40)

        while True:
            try:
                # 멘트 수정: 방문했던 장소를 묻는 형태로 변경
                user_input = input("\n사용자가 방문했던 장소의 번호를 공백으로 구분해 입력하세요 (예: 0 2): ")
                
                if not user_input.strip():
                    print("입력값이 없습니다. 다시 입력해주세요.")
                    continue

                input_indices = list(set(map(int, user_input.split())))

                # 유효성 검사
                invalid_indices = [idx for idx in input_indices if idx < 0 or idx >= len(self.goal_options)]
                if invalid_indices:
                    print(f"오류: 존재하지 않는 장소 번호입니다: {invalid_indices}")
                    continue
                
                return input_indices

            except ValueError:
                print("오류: 숫자만 입력해주세요.")

    def run_trace(self):
        self.navigator.info('Initializing User History Tracer...')

        # 1. 방문 이력 입력 받기
        visited_history = self.get_user_history()
        print(f"\n입력된 방문 이력: {visited_history}")

        if not visited_history:
            self.navigator.info("No history provided. Exiting.")
            return

        # 2. 최적 경로(순서) 계산
        # 로봇은 (0,0)에서 출발한다고 가정 (혹은 현재 위치 get_pose() 사용 가능)
        initial_pose = self.create_pose(0.0, 0.0, 0.0, 1.0) 
        
        self.navigator.info('Calculating best route to retrace steps...')
        best_route, _ = self.find_best_route_brute_force(initial_pose, visited_history)

        path_names = [self.goal_options[i]['name'] for i in best_route]
        print("\n" + "*"*50)
        print(f"  최적 탐색 경로: {' -> '.join(path_names)}")
        print("*"*50 + "\n")

        # 3. 주행 시작 (자취 따라가기)
        for index in best_route:
            target_name = self.goal_options[index]['name']
            target_pose = self.goal_options[index]['pose']

            self.navigator.info(f'Retracing path to {target_name}...')
            self.navigator.startToPose(target_pose)

            while not self.navigator.isTaskComplete():
                time.sleep(0.1)

            result = self.navigator.getResult()
            if result == TaskResult.SUCCEEDED:
                self.navigator.info(f'Checked {target_name} (Visited Spot).')
                time.sleep(2.0) # 탐색 시간
            elif result == TaskResult.CANCELED:
                self.navigator.info(f'Navigation to {target_name} was canceled.')
            elif result == TaskResult.FAILED:
                self.navigator.error(f'Failed to reach {target_name}.')

        self.navigator.info('History check completed. Returning to dock...')

def main(args=None):
    rclpy.init(args=args)
    
    # 클래스 인스턴스 생성 및 실행
    tracer = VisitedHistoryPatrol()
    tracer.run_trace()
    
    rclpy.shutdown()

if __name__ == '__main__':
    main()