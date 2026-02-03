import rclpy

from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator
from geometry_msgs.msg import PoseStamped,Quaternion

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
    

    # Prepare goal pose options
    goal_options = [
        # 입구 (Entrance)
        {'name': 'Entrance',
         'pose': create_pose(navigator, -3.26, 0.95, 0.9881, 0.1536)},

        # 은행 (Bank)
        # {'name': 'Bank',
        #  'pose': create_pose(navigator, -1.91, 0.71, 0.4327, 0.9015)},
        {'name': 'Bank',
         'pose': create_pose(navigator, -2.39, 0.35, 0.4327, 0.9015)},

        # 카운터 (Counter)
        {'name': 'Counter',
         'pose': create_pose(navigator, -0.54, 0.77, 0.7177, 0.6963)},

        # 벤치1 (Bench 1)
        {'name': 'Bench_1',
         'pose': create_pose(navigator, -0.54, -0.87, -0.7689, 0.6394)},

        # 벤치2 (Bench 2)
        {'name': 'Bench_2',
         'pose': create_pose(navigator, -0.83, -2.24, 0.58, 0.8146)},

        # 여자화장실 (Ladies Room)
        {'name': 'Ladies_Room',
         'pose': create_pose(navigator, -0.47, -3.87, -0.1166, 0.9931)},

        # Gate 1
        {'name': 'Gate_1',
         'pose': create_pose(navigator, -0.76, -4.44, -0.6276, 0.7785)},

        # Gate 2
        {'name': 'Gate_2',
         'pose': create_pose(navigator, -2.10, -4.16, -0.7512, 0.66)},

        # 면세점 (Duty Free)
        {'name': 'Duty_Free',
         'pose': create_pose(navigator, -2.22, -1.98, -0.9927, 0.1203)},

        # 남자화장실 (Mens Room)
        {'name': 'Mens_Room',
         'pose': create_pose(navigator, -3.29, -0.10, 0.9980, 0.0631)},

        {'name': 'Exit',
         'pose': None}
    ]

    navigator.info('Welcome to the mail delivery service.')

    while True:
        # Create a list of the goals for display
        options_str = 'Please enter the number corresponding to the desired robot goal position:\n'
        for i in range(len(goal_options)):
            options_str += f'    {i}. {goal_options[i]["name"]}\n'

        # Prompt the user for the goal location
        raw_input = input(f'{options_str}Selection: ')

        selected_index = 0

        # Verify that the value input is a number
        try:
            selected_index = int(raw_input)
        except ValueError:
            navigator.error(f'Invalid goal selection: {raw_input}')
            continue

        # Verify that the user input is within a valid range
        if (selected_index < 0) or (selected_index >= len(goal_options)):
            navigator.error(f'Goal selection out of bounds: {selected_index}')

        # Check for exit
        elif goal_options[selected_index]['name'] == 'Exit':
            selected_index = 0
            navigator.info('Going Home...')
            navigator.startToPose(goal_options[selected_index]['pose'])
            navigator.info('Docking before exiting')
            navigator.dock()
            break

        else:
            # Navigate to requested position
            navigator.startToPose(goal_options[selected_index]['pose'])

    rclpy.shutdown()


if __name__ == '__main__':
    main()
