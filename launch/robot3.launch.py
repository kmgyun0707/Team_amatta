import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    # 1. 네임스페이스 설정 (기본값: robot3)
    # 터미널에서 실행할 때 namespace:=robot99 처럼 바꿀 수도 있게 설정
    namespace_arg = DeclareLaunchArgument(
        'namespace',
        default_value='robot3',
        description='Top-level namespace'
    )
    ns = LaunchConfiguration('namespace')

    # 1. Turtlebot3 Nav2 패키지 경로 찾기
    # (주의: 사용 중인 Nav2 런치 파일이 있는 패키지 이름을 정확히 적어야 합니다. 보통 'turtlebot3_navigation2' 입니다.)
    nav2_pkg_dir = get_package_share_directory('turtlebot4_navigation')
    
    # 2. Nav2 런치 파일 포함시키기 (Include)
    # 'nav2.launch.py' 파일이 launch 폴더 안에 있다고 가정합니다.
    nav2_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_pkg_dir, 'launch', 'nav2.launch.py') # 런치 파일 이름 확인!
        ),
        launch_arguments={
            'use_sim_time': 'False',
            'namespace': ns,
        }.items()
    )

    # 3. 내 패키지 노드들 정의 (PC1용)
    perception_node = Node(
        package='amatta',
        executable='perception',
        name='perception_node_robot3',
        output='screen',
        namespace=ns,
        remappings=[
            ('/tf', ['/', ns, '/tf']),              # 결과: /robot3/tf
            ('/tf_static', ['/', ns, '/tf_static']) # 결과: /robot3/tf_static
        ]

    )

    guide_node = Node(
        package='amatta',
        executable='guide_to_info',
        name='guide_to_info_node',
        output='screen',
        namespace=ns
    )

    visited_node = Node(
        package='amatta',
        executable='visited_history_patrol',
        name='visited_history_patrol_node',
        output='screen',
        namespace=ns
    )

    # 4. LaunchDescription 리턴 (Nav2 + 내 노드들)
    return LaunchDescription([
        namespace_arg,
        nav2_launch_cmd,
        perception_node,
        guide_node,
        visited_node
    ])