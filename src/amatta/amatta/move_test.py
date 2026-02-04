import rclpy
import time

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

    
    visited_spots = [0, 1, 2, 3]        # 추후 DB에서 읽어오도록 수정 필요

    # Prepare goal pose options
    goal_options = [
        # 0 입구 (Entrance)
        {'name': 'Entrance',
         'pose': create_pose(navigator, -0.76, -1.59, 0.9881, 0.1536)},

        # 1 은행 (Bank)
        {'name': 'Bank',
         'pose': create_pose(navigator, -2.21, -1.61, 0.4327, 0.9015)},

        # 2 카운터 (Counter)
        {'name': 'Counter',
         'pose': create_pose(navigator, -2.35, 0.799, 0.7177, 0.6963)},

        # # 3 벤치1 (Bench 1)
        # {'name': 'Bench_1',
        #  'pose': create_pose(navigator, -0.584, 3.64, -0.7689, 0.6394)},

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
