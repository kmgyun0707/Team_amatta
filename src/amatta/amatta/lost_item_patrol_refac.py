import rclpy
import time
import math
import itertools
from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import TaskResult

class LostItemPatrol:
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

        # 4. 목표 지점(Goal Options) 정의
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

    def get_user_input(self):
        """사용자 입력을 받아 제외할 곳을 뺀 방문 리스트를 반환"""
        all_indices = list(range(len(self.goal_options)))
        
        print("\n" + "="*40)
        print("      [ 전체 장소 목록 ]")
        for i, option in enumerate(self.goal_options):
            print(f"  {i} : {option['name']}")
        print("="*40)

        while True:
            try:
                user_input = input("\n탐색에서 제외할 장소의 번호를 공백으로 구분해 입력하세요 (엔터 시 전체 탐색): ")
                
                # 입력이 없으면 전체 방문
                if not user_input.strip():
                    print("제외할 장소가 없습니다. 모든 장소를 탐색합니다.")
                    return all_indices

                input_indices = list(set(map(int, user_input.split())))

                # 유효성 검사
                invalid_indices = [idx for idx in input_indices if idx < 0 or idx >= len(self.goal_options)]
                if invalid_indices:
                    print(f"오류: 존재하지 않는 인덱스입니다: {invalid_indices}")
                    continue
                
                # 차집합 계산 (전체 - 제외)
                visited_spots = [idx for idx in all_indices if idx not in input_indices]
                return visited_spots

            except ValueError:
                print("오류: 숫자만 입력해주세요.")

    def run_patrol(self):
        # 1. 방문할 장소 결정
        visited_spots = self.get_user_input()
        print(f"\n최종 방문할 장소 인덱스: {visited_spots}")

        if not visited_spots:
            self.navigator.info("No targets selected. Exiting.")
            return

        self.navigator.info('Starting patrol service...')

        # 2. 최적 경로 계산
        # 현재 로봇의 위치(initial pose)를 시작점으로 설정
        # (주의: 실제 이동 후에는 get_pose_stamped() 등으로 현재 위치를 갱신해서 써야 할 수도 있음, 
        #  여기서는 초기 위치가 0,0이라고 가정하고 시작)
        current_robot_pose = self.goal_options[0]['pose'] # 임시: 타입 맞추기용, 실제론 (0,0) Pose 생성해서 넣는게 정확함.
        # 정확히 하려면:
        initial_pose = self.create_pose(0.0, 0.0, 0.0, 1.0) # 초기 위치
        
        best_route, _ = self.find_best_route_brute_force(initial_pose, visited_spots)

        path_names = [self.goal_options[i]['name'] for i in best_route]
        self.navigator.info(f'Optimized Route: {path_names}')

        # 3. 주행 시작
        for index in best_route:
            target_name = self.goal_options[index]['name']
            target_pose = self.goal_options[index]['pose']

            self.navigator.info(f'Navigating to {target_name}...')
            self.navigator.startToPose(target_pose)

            while not self.navigator.isTaskComplete():
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
    patrol_robot.run_patrol()
    
    rclpy.shutdown()

if __name__ == '__main__':
    main()