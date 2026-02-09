# Amatta! (Airport Lost and Found Robot)
# 아마따! (공항 분실물 관리 로봇)

- ROKEY 부트캠프 6기 E1조, E3조 "아마따!" 팀의 프로젝트 레포지토리입니다.

# 1. 프로젝트 개요
### 1.1 개발 목적
 - 인천국제공항 내 연간 약 6만 건에 달하는 분실물 발생 및 그중 50%가 미회수되는 문제를 해결하기 위해,
   기존의 수동적이고 보관 중심적인 유실물 관리 시스템을 로봇 기반의 능동적 탐색 체계로 전환하여 골든 타임을 확보하는 것을 목표로 합니다.

   **YOLO11n 기반 객체 인식**
   C3k2 Block을 활용한 특징 추출 강화로 작은 객체 인식을 정밀화하고 오탐지율을 최소화합니다.

   **다중 로봇 협업 및 최적 경로 생성**
   사용자의 이동 경로를 역추적하거나 분실 다발 구역을 집중 수색하며, Brute Force 알고리즘을 통해 이동 거리를 최소화하는 최적의 탐색 동선을 구축합니다.
   
   **웹·서버·DB 통합 모니터링 시스템**
   Flask와 SQLite를 활용하여 분실물 정보를 실시간으로 관리하고, 로봇의 상태 및 탐색 결과가 자동으로 업데이트되는 자동화 관리 체계를 결합합니다.

    이를 통해 로봇의 능동적 탐색 역량과 분실물 회수 업무의 효율성을 동시에 확보하여 연간 약 1만 시간 이상의 업무 절감 효과를 창출하는 것을 목표로 합니다.

### 1.2 개발 기간
 - 2026.02.02 ~ 2026.02.09 (8일)

# 2. Team Members
  
| **김명균** | **이정현** | **이한빈** | **이주노**| **이채영**| **지승아** | **곽문정** | **진재협**|
|:------:|:------:|:------:|:------:|:------:|:------:|:------:|:------:
| <img src="https://github.com/user-attachments/assets/8c9a73f5-eb3f-43e9-b948-5df4af6962b2" alt="김명균" width="150"> | <img src="https://github.com/user-attachments/assets/83b67e17-3244-4a29-b00a-d53c72003ac2" alt="이정현" width="150"> | <img src="https://github.com/user-attachments/assets/0b5235c8-dc9d-45c8-a7dc-643f75ee4658" alt="이한빈" width="150"> | <img src="https://github.com/user-attachments/assets/ab667249-9c97-48f9-a814-98c1ddb2e596" alt="이주노" width="150"> |<img src="https://github.com/user-attachments/assets/68f09f42-26f0-43e1-a1c2-be847abdf51b" alt="이채영" width="150"> | <img src="https://github.com/user-attachments/assets/080978f8-b11d-4d55-8fc1-f2a343c55800" alt="지승아" width="150"> | <img src="https://github.com/user-attachments/assets/1085c3e9-daaa-4ab1-b9c1-4b6521022498" alt="곽문정" width="150"> | <img src="https://github.com/user-attachments/assets/a343d99d-e1ab-4d95-86e5-ebcddd00bafc" alt="진재협" width="150"> |
| PM | Detection | Detection | FE/DB | FE/DB | AMR | AMR | AMR |
| [GitHub](https://github.com/kmgyun0707) | [GitHub](https://github.com/jhlgitloop) | [GitHub](https://github.com/ddiw) | [GitHub](https://github.com/dlwnsh925) | [GitHub](https://github.com/yichaeyoung) | [GitHub](https://github.com/seounga) | [GitHub](https://github.com/merong564) | [GitHub](https://github.com/comport98) |


# 3. 실행 가이드

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

### 3.3 프로젝트 실행
Isaac Sim 확장 및 물리 엔진과 연동된 Python 환경에서 프로젝트를 실행합니다.

```bash
git clone -b develop https://github.com/merong564/DTHRC.git
cd ~/Desktop/DTHRC/DTHRC
./python.sh /home/rokey/Desktop/DTHRC/DTHRC/main.py
```

# 4. 폴더 구조

### Robot Folder
```plaintext
project/
├── config/
│   └── nav2_amatta.yaml
├── launch/
│   └── robot3.launch.py
├── maps/
│   ├── map.pgm
│   └── map.yaml
├── model/
│   └── best.pt
├── src/
│   ├── amatta
│   │   └── amatta 
│   │       ├── guide_to_info.py
│   │       ├── lost_spot_patrol.py    
│   │       ├── perception.py
│   │       └── visited_history_patrol.py                   
│   ├── airport_guide_interfaces
│   │   └── msg
│   │       ├── Dbinfo.msg
│   │       └── DetectionInfo.msg                   
│   └── my_robot_interfaces
│       └── msg
│           └── DetectionResult.msg                   
├── src/
│   └── rmpflow_controller.py     
└── README.md
```

### Web Folder
```plaintext
project/
├── sql/
│   ├── amatta.db
│   ├── column.sql
│   └── lost_item.sql
├── src/
│   ├── airport_guide_interfaces
│   └── my_robot_interfaces
├── static/
├── template/
│   ├── user_login_center.html
│   ├── user_item.html
│   ├── search_start.py
│   ├── search_success.html
│   ├── search_fail.html
│   ├── lost_report.html
│   ├── item.html
│   ├── guide_start.html
│   ├── ad_login_center.html
│   ├── ad_login.html
│   ├── ad_graph_test.html
│   ├── ad_graph.html
│   └── ad_detect.html
├── web/
│   ├── user_load_db.py
│   ├── test_pub_dbinfo.py
│   ├── search_start.py
│   ├── ros_monitor.py
│   ├── lost_test.py
│   ├── lost_report.py
│   ├── location_mapper.py
│   ├── guide_start.py
│   ├── ad_load_db.py
│   ├── location_mapper.py
│   ├── ad_graph.py
│   └── ad_detect.py
├── api_test.py
├── found_item_listener.py
├── result_listener.py                 
├── test_dbinfo_subscriber.py
├── main.py
├── user_item_list_qr.png
└── README.md
```

# 5. 주요 기능

### 5.1  AMR Control (Nav2 & FSM)
 - 실시간 협동 경로 생성 : 두 대의 AMR이 작업 구역을 분담하여 사각지대를 해소하고 최적의 탐색 동선을 생성합니다.
 - 시나리오 기반 상태 제어 (FSM):
   - Stand-by: QR 신고 접수 및 대기 
   - Path Planning: 신고자 이동 경로 역추적 및 최적 경로 계산 
   - Scanning: YOLO 기반 분실물 탐색 수행
   - Recovery: 분실물 발견 및 수거
   - Delivery: 지정 게이트로 물품 전달 및 업무 종료

### 5.2 Perception (YOLO11n)
 - 분실물 실시간 객체 인식 : 지갑, 스마트폰, 여권 등 주요 분실물을 탐지합니다.
 - 최적 모델 선정 및 성능:
   -  모델: YOLO11n (C3k2 Block 기반 특징 추출 강화)
   -  정확도: mAP50 기준 94.26% 달성
   -  지연율: 1.55ms의 추론 속도로 통신 지연 상쇄 및 안전 마진 확보

### 5.3 System Integration & Monitoring
 - 웹-로봇 실시간 동기화 : Flask 기반 웹 인터페이스와 ROS2 토픽 통신을 통합하여 데이터 누락 없는 업로드를 구현합니다.
 - 3단계 관리 시스템:
   - 안내 모드: 습득물 DB 존재 시 보관소까지 길 안내 수행
   - 탐색 모드: 미등록 물품 신고 시 로봇이 직접 순찰 및 탐지
   - 관리 모드: 실시간 로봇 상태(배터리, 좌표) 및 DB 업데이트 모니터링

# 6. 기술 스택 및 개발 환경

<div style="display:flex; flex-direction:row;">
  <img src="https://img.shields.io/badge/ubuntu-E95420?style=flat&logo=Python&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat&logo=Python&logoColor=white" />
  <img src="https://img.shields.io/badge/nvidia-76B900?style=flat&logo=nvidia&logoColor=white" />
  <img src="https://img.shields.io/badge/yolo-111F68?style=flat&logo=nvidia&logoColor=white" />
 <img src="https://img.shields.io/badge/ros-22314E?style=flat&logo=Python&logoColor=white" />
  <img src="https://img.shields.io/badge/rockwellautomation-CD163F?style=flat&logo=Python&logoColor=white" />
 <img src="https://img.shields.io/badge/opencv-5C3EE8?style=flat&logo=Python&logoColor=white" />
 <img src="https://img.shields.io/badge/jira-0052CC.svg?&style=flaat&logo=github&logoColor=white" />
 <img src="https://img.shields.io/badge/raspberrypi-A22846.svg?&style=flat&logo=notion&logoColor=white" />
  <img src="https://img.shields.io/badge/flask-3BABC3?style=flat&logo=nvidia&logoColor=white" />
  <img src="https://img.shields.io/badge/sqlite-003B57?style=flat&logo=nvidia&logoColor=white" />
  <img src="https://img.shields.io/badge/github-%23181717.svg?&style=flaat&logo=github&logoColor=white" />
  <img src="https://img.shields.io/badge/notion-%23000000.svg?&style=flat&logo=notion&logoColor=white" />
  <img src="https://img.shields.io/badge/jira-0052CC.svg?&style=flaat&logo=github&logoColor=white" />
 <img src="https://img.shields.io/badge/googledrive-4285F4.svg?&style=flat&logo=notion&logoColor=white" />
  <img src="https://img.shields.io/badge/googlegemini-8E75B2.svg?&style=flaat&logo=github&logoColor=white" />
</div><br>
