# 뎁스 이미지와 RGB 이미지를 동기화하여 YOLO 모델로 물체를 인식하고,
# 인식된 물체의 3D 좌표를 계산하여 로봇 내비게이션 시스템에 전달하는 ROS2 노드입니다.

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo, CompressedImage
from geometry_msgs.msg import PoseStamped

from geometry_msgs.msg import PointStamped
from tf2_ros import Buffer, TransformListener
from cv_bridge import CvBridge
import numpy as np
import cv2
import message_filters
from ultralytics import YOLO
import time # 처리 시간 계산용
from rclpy.qos import QoSProfile, ReliabilityPolicy
import tf2_geometry_msgs
from tf2_geometry_msgs.tf2_geometry_msgs import do_transform_point
from rclpy.time import Time
from rclpy.duration import Duration 
from my_robot_interfaces.msg import DetectionResult # DB 저장용
from airport_guide_interfaces.msg import DetectionInfo  # Navigator 알림용
from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator




class Detect_to_Lossitem(Node):
    def __init__(self, model):
        super().__init__('detect_to_lossitem')
        self.get_logger().info('=== Detect_to_Lossitem 노드 초기화 시작 ===')
        
        self.navigator = TurtleBot4Navigator()

        self.bridge = CvBridge()
        self.model = model
        self.classNames = model.names
        self.K = None
        
        # __init__ 내부 수정
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            depth=2
        )

        self.name_space = self.get_namespace()
        # self.get_logger().info(f'현재 네임스페이스: {ns}')

        # Camera Info (단 한 번만 성공 로그를 찍기 위한 플래그)
        self.info_received = False
        self.info_sub = self.create_subscription(CameraInfo, f'{self.name_space}/oakd/rgb/camera_info', self.camera_info_callback, 1)
        
        # Message Filters
        self.rgb_sub = message_filters.Subscriber(self, CompressedImage, f'{self.name_space}/oakd/rgb/image_raw/compressed',qos_profile=qos_profile)
        self.depth_sub = message_filters.Subscriber(self, Image, f'{self.name_space}/oakd/stereo/image_raw',qos_profile=qos_profile)
        # slop은 환경에 따라 0.05~0.2 사이에서 조절하세요.
        self.ts = message_filters.ApproximateTimeSynchronizer([self.rgb_sub, self.depth_sub], 100, 0.5) #수정 
        self.ts.registerCallback(self.synchronized_callback)
     
        self.is_detected = self.create_publisher(DetectionInfo, f'{self.name_space}/is_detected',10) # 이건 네임스페이스 없이 발행
        self.db_pub = self.create_publisher(DetectionResult, '/db_post',10) 
        self.loss_item_view_pub = self.create_publisher(Image, f'{self.name_space}/tracking', 10)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.detected = False
        self.get_logger().info('구독 및 필터 설정 완료. 데이터를 기다리는 중...')
        self.goal_sent = False #[추가] 목표가 전송되었는지 여부 추적 변수

    def camera_info_callback(self, msg):
        if not self.info_received:
            self.K = np.array(msg.k).reshape(3, 3)
            self.get_logger().info('카메라 내부 파라미터(K) 수신 완료!')
            self.info_received = True

    # 동기화된 RGB 및 뎁스 이미지 콜백
    def synchronized_callback(self, rgb_msg, depth_msg):
        start_time = time.time() # 성능 모니터링 시작
        frame_id = getattr(self, 'camera_frame', None) 
        
        # 카메라 정보가 아직 수신되지 않은 경우 처리 건너뛰기
        if self.K is None:
            self.get_logger().warn('카메라 정보(K)가 아직 없어 처리를 건너뜁니다.', throttle_duration_sec=5.0)
            return
         
        if depth_msg : # [수정] depth_msg가 true일때만 실행
            try:
                # 1. 데이터 디코딩
                np_arr = np.frombuffer(rgb_msg.data, np.uint8) # CompressedImage to numpy array
                rgb_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR) # numpy array to OpenCV image
                depth_img = self.bridge.imgmsg_to_cv2(depth_msg, desired_encoding='passthrough')# Image to OpenCV image
                frame_id = depth_msg.header.frame_id # 뎁스 이미지의 frame_id 사용
                # self.get_logger().info(f"frame_id: {frame_id}") # 로그 추가
                # self.get_logger().info(f"rgb_msg.header.frame_id: {rgb_msg.header.frame_id}") # 로그 추가
                
                # 2. YOLO 추론
                results = self.model.predict(rgb_img, verbose=False, conf=0.5 ,device ='0') # GPU 사용 시 '0', CPU 사용 시 'cpu'

                #[추가] detected 초기화
                self.detected = False
                for r in results: # 각 프레임에 대한 결과
                    if len(r.boxes) == 0: # 검출된 객체가 없으면 건너뜀 - 추가 
                        self.get_logger().info("검출된 객체 없음") # 로그 추가
                        continue
                    self.detected = True #[추가] 탐지 됐다고 true해야하는데 아예빠져있어서 추가... 빠져있던 부분...
                    sorted_boxes = sorted(r.boxes, key=lambda b: b.conf[0], reverse=True)#각 객체가 아닌 제일 신뢰도가 높은 객체 하나만 처리하도록 [수정]
                    for box in sorted_boxes[:1]: # 신뢰도 상위 1개 객체만 처리
                        x1, y1, x2, y2 = map(int, box.xyxy[0]) # 바운딩 박스 좌표
                        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2 #중심점

                        cls_id = int(box.cls[0]) # 클래스 ID
                        label_name = self.classNames[int(box.cls[0])] if int(box.cls[0]) < len(self.classNames) else "Unknown" # 클래스 이름
                        confidence = float(box.conf[0]) # 신뢰도

                        # 이미지 범위 체크 (IndexError 방지)
                        if cy >= depth_img.shape[0] or cx >= depth_img.shape[1]:
                            continue

                        # z = float(depth_img[cy, cx]) / 1000.0 # 깊이 값 (mm -> m) 
                        #정중앙값 1개만 읽어오는게 아닌 5x5 영역의 중앙값으로 읽어오도록 수정
                        depth_values = depth_img[max(0, cy-2):min(depth_img.shape[0], cy+3), max(0, cx-2):min(depth_img.shape[1], cx+3)]
                        z = float(np.median(depth_values)) / 1000.0 # 깊이 값 (mm -> m)

                        #확인 로그 추가
                        self.get_logger().info(f'검출된 객체: {label_name}, 신뢰도: {confidence}, 깊이 값(z): {z}m')
                        if z <= 0.1 or z > 2.2: # 유효 거리 범위 체크 (0.1m ~ 5.0m) 
                            continue

                        # 3. 2D->3D 좌표 변환
                        pt_camera = PointStamped() # 카메라 프레임의 3D 포인트
                        # pt_camera.header.stamp = Time().to_msg() # 시간 동기화, [수정] 이거 그대로 timestamp 안맞아서 오류나는 경우가 있어서 현재 시간으로 덮음
                        pt_camera.header.stamp = Time(seconds=0).to_msg()  # 타임스탬프를 0으로 설정하여 최신 변환 사용
                        pt_camera.header.frame_id = frame_id # 카메라 프레임
                        
                        fx, fy, ox, oy = self.K[0,0], self.K[1,1], self.K[0,2], self.K[1,2] # 카메라 내부 파라미터
                        pt_camera.point.x = (cx - ox) * z / fx # 3D 좌표 계산
                        pt_camera.point.y = (cy - oy) * z / fy # 3D 좌표 계산
                        pt_camera.point.z = z # 깊이 값


                        try:
                            target_frame = 'map'
                            pt_map = self.tf_buffer.transform(pt_camera, target_frame, timeout=Duration(seconds=1.0)) # 'map' 프레임으로 변환

                            #좌표 변환 성공 로그
                            self.get_logger().info(f'TF 변환 성공: {pt_camera.point.x:.2f}, {pt_camera.point.y:.2f} -> {pt_map.point.x:.2f}, {pt_map.point.y:.2f}')
                            goal_pose = PoseStamped() # 목표 위치 생성
                            goal_pose.header.frame_id = 'map' # 'map' 프레임 
                            goal_pose.header.stamp = self.get_clock().now().to_msg() # 현재 시간
                            goal_pose.pose.position.x = pt_map.point.x # 목표 위치 x설정
                            goal_pose.pose.position.y = pt_map.point.y # 목표 위치 y설정
                            goal_pose.pose.position.z = 0.0  # 평면 이동 가정 z축 0 설정
                            goal_pose.pose.orientation.w = 1.0  # 방향 설정 (회전 없음) -> 아마 이거 없어서 명령이 안먹혔던 것 같음 [추가]

                            self.goal = goal_pose # 목표 위치 저장

                            # 발행할 메시지
                            detect_msg = DetectionInfo() 
                            detect_msg.goal = self.goal # 목표 위치 포함 )
                            detect_msg.detected = self.detected # 탐지 여부 포함 
                            self.is_detected.publish(detect_msg)# /is_detected 발행
                            
                            if not self.goal_sent:  # 목표가 아직 전송되지 않은 경우에만
                                self.goal_sent = True  # 목표가 전송되었음을 표시
                                # self.navigator.startToPose(detect_msg.goal) # 내비게이션 시작
                            # 검출 정보 로깅
                            self.get_logger().info(f'[{label_name}] 발견! 위치: x={pt_map.point.x:.2f}, y={pt_map.point.y:.2f}, 거리={z:.2f}m')

                            # 시각화
                            label = f"{label_name} ({pt_map.point.x:.1f}, {pt_map.point.y:.1f})"
                            cv2.rectangle(rgb_img, (x1, y1), (x2, y2), (0, 0, 255), 2)
                            cv2.putText(rgb_img, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                            
                            # DB 저장용 메시지 발행
                            # db_msg = DetectionResult()
                            # db_msg.item_name = label_name
                            # db_msg.position.x = pt_map.point.x
                            # db_msg.position.y = pt_map.point.y
                            # db_msg.position.z = 0.0
                            # self.db_pub.publish(db_msg)
                        except Exception as e:
                            self.get_logger().error(f'❌ 실패: {e}')
                            # [추가] 도대체 로봇이 알고 있는 프레임은 뭐가 있는지 족보를 다 출력해라!
                            self.get_logger().info(f'📜 현재 TF 족보: {self.tf_buffer.all_frames_as_string()}')

                            continue
                # 4. 결과 발행 및 성능 로그
                out_msg = self.bridge.cv2_to_imgmsg(rgb_img, encoding="bgr8") # OpenCV 이미지 -> ROS Image 메시지
                self.loss_item_view_pub.publish(out_msg) # 시각화 이미지 발행
                
                end_time = time.time() # 성능 모니터링 종료
                processing_ms = (end_time - start_time) * 1000 # 처리 시간 계산 (ms)

            except Exception as e:
                self.get_logger().error(f'콜백 실행 중 예외 발생: {e}')




def main(args=None):

#     # [추가]네임스페이스 및 TF 리매핑 설정 
#     import sys

#     if args is None:
#         args = sys.argv
#     if '--ros-args'not in args:
#         args.append('--ros-args')
#     args.append('-r')
#     args.append('__ns:=/robot1')  # 네임스페이스 설정
    
#     args.append('-r')
#     args.append('/tf:=/robot1/tf')  # tf 토픽 네임스페이스 설정
#     args.append('-r')
#     args.append('/tf_static:=/robot1/tf_static')  # tf_static 토
# ######################################################################

    # 경로 확인 비판: 파일이 실제로 있는지 확인하는 로직을 넣으면 더 좋습니다.
    model_path = '/home/rokey/Desktop/Team_amatta/model/model2.pt'
    model = YOLO(model_path)
    
    rclpy.init(args=args)
    node = Detect_to_Lossitem(model)
    node.get_logger().info('스핀(Spin) 시작 - 메시지 대기 중...')
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().warn('Keyboard Interrupt 수신 (Ctrl+C).')
    finally:
        node.get_logger().info('노드를 종료하고 리소스를 해제합니다.')
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()