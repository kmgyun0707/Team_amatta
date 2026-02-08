# Team Amatta Execution Guide

## 유의사항
1. 모든 터미널은 실행 전 **`ws`** (워크스페이스 소싱) 필수입니다.
2. Localization/Navigation 실행 전에는 `ros-restart`를 권장합니다.
3. 코드 수정 시 `wb` -> `ws` 순서로 빌드하세요.

---

## PC 1 (MSI) - Robot 1 구동 & 통합 제어

아래 명령어들은 각각 **새로운 터미널 창**을 열어서 순서대로 실행하세요.

### 1. Localization (위치 추정)
```bash
# [Terminal 1]
ws
ros-restart

# Alias 사용 시
robot-loc
# 또는 Full Command
ros2 launch turtlebot4_navigation localization.launch.py namespace:=/robot1 map:=/home/rokey/Desktop/Team_amatta/maps/map.yaml
```

### 2. RViz (시각화 및 초기 위치 설정)
실행 후 상단 '2D Pose Estimate'로 초기 위치를 잡아주세요.

```Bash
# [Terminal 2]
ws

# Alias 사용 시
robot-view
# 또는 Full Command
ros2 launch turtlebot4_viz view_robot.launch.py namespace:=/robot1
```

### 3. Navigation (자율 주행)
RViz에서 Costmap이 정상적으로 뜨는지 확인하세요.

``` Bash
# [Terminal 3]
ws
ros-restart

# Alias 사용 시
robot-nav
# 또는 Full Command
ros2 launch turtlebot4_navigation nav2.launch.py namespace:=/robot1 params_file:=/home/rokey/Desktop/Team_amatta/config/nav2_amatta.yaml
```

### 4. Guide Node (가이드 모드)
```Bash
# [Terminal 4]
ws
ros2 run amatta guide --ros-args -r __ns:=/robot1
```

### 5. Visited History Node (사용자 경로 추적)
```Bash
# [Terminal 5]
ws
ros2 run amatta visited --ros-args -r __ns:=/robot1
```

### 6. Test DB (테스트용 DB 발행)
사용자 시나리오를 테스트할 때 실행하세요.

``` Bash
# [Terminal 6]
ws
ros2 run amatta test_db
```
**[입력 가이드]**

모드 선택: 가이드 모드(1) 또는 추적 모드(0)

추적 모드(0) 선택 시:

경로 입력: 6 3 0 2 (순서를 섞어서 입력하여 최단 경로 로직 확인)

게이트 입력: 8 또는 9


### 7. Test YOLO (Robot 1 인지 테스트)
```Bash
# [Terminal 7]
ws
ros2 run amatta test_yolo --ros-args -r __ns:=/robot1
```
**[입력 가이드] 1 입력 시 탐지 성공(정지), 0 입력 시 탐지 해제**


## PC 2 (Victus) - Robot 3 구동
아래 명령어들은 각각 새로운 터미널 창을 열어서 순서대로 실행하세요.

### 1. Localization (위치 추정)
```Bash
# [Terminal 1]
ws
ros-restart

# Alias 사용 시 (설정된 경우)
robot-loc
# 또는 Full Command
ros2 launch turtlebot4_navigation localization.launch.py namespace:=/robot3 map:=/home/rokey/Desktop/Team_amatta/maps/map.yaml
```

### 2. RViz (시각화 및 초기 위치 설정)
실행 후 상단 '2D Pose Estimate'로 초기 위치를 잡아주세요.

``` Bash
# [Terminal 2]
ws

# Alias 사용 시
robot-view
# 또는 Full Command
ros2 launch turtlebot4_viz view_robot.launch.py namespace:=/robot3
```

### 3. Navigation (자율 주행)
``` Bash
# [Terminal 3]
ws
ros-restart

# Alias 사용 시
robot-nav
# 또는 Full Command
ros2 launch turtlebot4_navigation nav2.launch.py namespace:=/robot3 params_file:=/home/rokey/Desktop/Team_amatta/config/nav2_amatta.yaml
```

### 4. Lost Item Node (분실물 수색 모드)
``` Bash
# [Terminal 4]
ws
ros2 run amatta lost --ros-args -r __ns:=/robot3
```

### 5. Test YOLO (Robot 3 인지 테스트)
```Bash
# [Terminal 5]
ws
ros2 run amatta test_yolo --ros-args -r __ns:=/robot3
```
**[입력 가이드] 1 입력 시 탐색 성공(정지), 0 입력 시 탐색 진행**

### 6. Test YOLO (Robot 1 인지 테스트)
```Bash
# [Terminal 6]
ws
ros2 run amatta test_yolo --ros-args -r __ns:=/robot3
```
**[입력 가이드] 1 입력 시 탐색 성공(정지), 0 입력 시 탐색 진행**


### 토픽 모니터링 (Topic Echo)
데이터 흐름을 확인하려면 아래 명령어를 사용하세요.

```Bash
# DB 데이터 확인 (Registered Info)
ros2 topic echo /is_registered

# 탐색 모드 상태 확인
ros2 topic echo /search_mode

# Robot 1 분실물 탐지 신호
ros2 topic echo /robot1/is_detected

# Robot 3 분실물 탐지 신호
ros2 topic echo /robot3/is_detected
```