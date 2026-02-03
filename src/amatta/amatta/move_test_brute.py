import rclpy
import time
# Brute Force 계산
import math
import itertools  # 순열 생성을 위한 라이브러리

from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import TaskResult


def create_pose(navigator, position_x, position_y, orientation_z, orientation_w):
    pose = PoseStamped()
    pose.header.frame_id = 'map'
    pose.header.stamp = navigator.get_clock().now().to_msg()
    
    # 위치 설정
    pose.pose.position.x = float(position_x)
    pose.pose.position.y = float(position_y)
    pose.pose.position.z = 0.0
    
    # 방향 설정 (제공해주신 쿼터니언 값 적용)
    pose.pose.orientation.x = 0.0
    pose.pose.orientation.y = 0.0
    pose.pose.orientation.z = float(orientation_z)
    pose.pose.orientation.w = float(orientation_w)
    
    return pose

# 두 Pose 사이의 유클리드 거리 계산 함수
def get_distance(pose1, pose2):
    x1 = pose1.pose.position.x
    y1 = pose1.pose.position.y
    x2 = pose2.pose.position.x
    y2 = pose2.pose.position.y
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

# Brute Force로 최적 경로 찾는 함수: 최소 이동 거리
def find_best_route_brute_force(start_pose, spots_indices, goal_options):
    min_distance = float('inf')
    best_order = []
    
    # spots_indices의 모든 순열(Permutations) 생성
    # 예: [0, 6, 3, 8] -> (0, 6, 3, 8), (0, 6, 8, 3), ... 총 4! = 24가지
    possible_paths = itertools.permutations(spots_indices)
    
    for path in possible_paths:
        current_distance = 0.0
        current_pose = start_pose
        
        for idx in path:
            target_pose = goal_options[idx]['pose']
            
            # 현재 위치에서 다음 목표까지의 거리 누적
            dist = get_distance(current_pose, target_pose)
            current_distance += dist
            
            # 로봇이 이동했다고 가정하고 현재 위치 업데이트
            current_pose = target_pose
        
        if current_distance < min_distance:
            min_distance = current_distance
            best_order = list(path)
            
    return best_order, min_distance

def main(args=None):
    rclpy.init(args=args)

    navigator = TurtleBot4Navigator()

    # Start on dock
    if not navigator.getDockedStatus():
        navigator.info('Docking before intialising pose')
        navigator.dock()

    # Set initial pose
    initial_pose = navigator.getPoseStamped([0.0, 0.0], TurtleBot4Directions.NORTH)
    navigator.setInitialPose(initial_pose)

    # Wait for Nav2
    navigator.waitUntilNav2Active()

    # Undock
    navigator.undock()

    
    visited_spots = [0, 6, 3, 8]        # 추후 DB에서 읽어오도록 수정 필요

    # Prepare goal pose options
    goal_options = [
        # 0 입구 (Entrance)
        {'name': 'Entrance',
         'pose': create_pose(navigator, -3.26, 0.95, 0.9881, 0.1536)},

        # 1 은행 (Bank)
        {'name': 'Bank',
         'pose': create_pose(navigator, -1.91, 0.71, 0.4327, 0.9015)},

        # 2 카운터 (Counter)
        {'name': 'Counter',
         'pose': create_pose(navigator, -0.54, 0.77, 0.7177, 0.6963)},

        # 3 벤치1 (Bench 1)
        {'name': 'Bench_1',
         'pose': create_pose(navigator, -0.54, -0.87, -0.7689, 0.6394)},

        # 4 벤치2 (Bench 2)
        {'name': 'Bench_2',
         'pose': create_pose(navigator, -0.83, -2.24, 0.58, 0.8146)},

        # 5 여자화장실 (Ladies Room)
        {'name': 'Ladies_Room',
         'pose': create_pose(navigator, -0.47, -3.87, -0.1166, 0.9931)},

        # 6 Gate 1
        {'name': 'Gate_1',
         'pose': create_pose(navigator, -0.76, -4.44, -0.6276, 0.7785)},

        # 7 Gate 2
        {'name': 'Gate_2',
         'pose': create_pose(navigator, -2.10, -4.16, -0.7512, 0.66)},

        # 8 면세점 (Duty Free)
        {'name': 'Duty_Free',
         'pose': create_pose(navigator, -2.22, -1.98, -0.9927, 0.1203)},

        # 9 남자화장실 (Mens Room)
        {'name': 'Mens_Room',
         'pose': create_pose(navigator, -3.29, -0.10, 0.9980, 0.0631)}
    ]

    navigator.info('Welcome to the mail delivery service.')

    # visited_spots 순서대로 탐색
    for index in visited_spots:
        if index < 0 or index >= len(goal_options):
            navigator.error(f'Invalid index: {index}. Skipping.')
            continue

        target_name = goal_options[index]['name']
        target_pose = goal_options[index]['pose']

        navigator.info(f'Navigating to {target_name}...')
        
        # 1. 이동 명령 전송 (비동기)
        navigator.startToPose(target_pose)

        # 2. 이동 완료까지 대기 (필수)
        while not navigator.isTaskComplete():
            time.sleep(0.1) # 0.1초씩 쉬면서 대기 (안하면 다른 작업 못 함)
            pass

        # 3. 결과 확인
        result = navigator.getResult()
        if result == TaskResult.SUCCEEDED:
            navigator.info(f'Arrived at {target_name}!')
            # 도착 후 잠시 대기
            time.sleep(2.0) 

        elif result == TaskResult.CANCELED:
            navigator.info(f'Navigation to {target_name} was canceled.')

        elif result == TaskResult.FAILED:
            navigator.error(f'Failed to reach {target_name}.')

    
    # 모든 순찰 종료
    navigator.info('All tasks completed. Returning to dock...')
    rclpy.shutdown()


if __name__ == '__main__':
    main()
