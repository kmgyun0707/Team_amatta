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




class Detect_to_Lossitem(Node):
    def __init__(self, model):
        super().__init__('detect_to_lossitem')
        self.get_logger().info('=== Detect_to_Lossitem 노드 초기화 시작 ===')
        
        self.bridge = CvBridge()
        self.model = model
        self.classNames = model.names
        self.K = None
        
        # __init__ 내부 수정
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            depth=10
        )

        ns = self.get_namespace()
        self.get_logger().info(f'현재 네임스페이스: {ns}')

        # Camera Info (단 한 번만 성공 로그를 찍기 위한 플래그)
        self.info_received = False
        self.info_sub = self.create_subscription(CameraInfo, f'{ns}/oakd/rgb/camera_info', self.camera_info_callback, 1)
        
        # Message Filters
        self.rgb_sub = message_filters.Subscriber(self, CompressedImage, f'{ns}/oakd/rgb/image_raw/compressed',qos_profile=qos_profile)
        self.depth_sub = message_filters.Subscriber(self, Image, f'{ns}/oakd/stereo/image_raw',qos_profile=qos_profile)

        # slop은 환경에 따라 0.05~0.2 사이에서 조절하세요.
        self.ts = message_filters.ApproximateTimeSynchronizer([self.rgb_sub, self.depth_sub], 10, 3)
        self.ts.registerCallback(self.synchronized_callback)
     
        self.is_detected = self.create_publisher(DetectionInfo, '/is_detected',10)
        self.db_pub = self.create_publisher(DetectionResult, '/db_post',10)
        self.loss_item_view_pub = self.create_publisher(Image, f'{ns}/tracking', 10)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.detected = False
        self.get_logger().info('구독 및 필터 설정 완료. 데이터를 기다리는 중...')

    def camera_info_callback(self, msg):
        if not self.info_received:
            self.K = np.array(msg.k).reshape(3, 3)
            self.get_logger().info('카메라 내부 파라미터(K) 수신 완료!')
            self.info_received = True

    def synchronized_callback(self, rgb_msg, depth_msg):
        start_time = time.time() # 성능 모니터링 시작
        frame_id = getattr(self, 'camera_frame', None)

        self.detected = False
        
        if self.K is None:
            self.get_logger().warn('카메라 정보(K)가 아직 없어 처리를 건너뜁니다.', throttle_duration_sec=5.0)
            return

        try:
            # 1. 데이터 디코딩
            np_arr = np.frombuffer(rgb_msg.data, np.uint8)
            rgb_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            depth_img = self.bridge.imgmsg_to_cv2(depth_msg, desired_encoding='passthrough')
            frame_id = depth_msg.header.frame_id
            self.get_logger().info("frame_id")
            self.get_logger().info("rgb_msg.header.frame_id")
            
            # 2. YOLO 추론
            results = self.model.predict(rgb_img, verbose=False, conf=0.3)
            
            num_detected = 0
            for r in results:
                self.detected = True
                num_detected += len(r.boxes)
                for box in r.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2 #중심점
                    label_name = self.classNames[int(box.cls[0])] if int(box.cls[0]) < len(self.classNames) else "Unknown"
                    # 이미지 범위 체크 (IndexError 방지)
                    if cy >= depth_img.shape[0] or cx >= depth_img.shape[1]:
                        continue

                    z = float(depth_img[cy, cx]) / 1000.0
                    if z <= 0.1 or z > 5.0:
                        continue

                    # 3. 좌표 변환
                    pt_camera = PointStamped()
                    pt_camera.header.stamp = depth_msg.header.stamp
                    pt_camera.header.frame_id = frame_id
                    
                    fx, fy, ox, oy = self.K[0,0], self.K[1,1], self.K[0,2], self.K[1,2]
                    pt_camera.point.x = (cx - ox) * z / fx
                    pt_camera.point.y = (cy - oy) * z / fy
                    pt_camera.point.z = z

                    try:
                        pt_map = self.tf_buffer.transform(pt_camera, 'map', timeout=Duration(seconds=1.0))
                        

                        goal_pose = PoseStamped()
                        goal_pose.header.frame_id = 'map'
                        goal_pose.header.stamp = self.get_clock().now().to_msg()
                        goal_pose.pose.position.x = pt_map.point.x
                        goal_pose.pose.position.y = pt_map.point.y
                        goal_pose.pose.position.z = 0.0
                        # yaw = 0.0
                        # qz = math.sin(yaw / 2.0)
                        # qw = math.cos(yaw / 2.0)
                        # car view orientation
                        # qz = -0.775
                        # qw =  0.632
                        # goal_pose.pose.orientation = Quaternion(x=0.0, y=0.0, z=qz, w=qw)

                        self.goal = goal_pose

                        # 발행할 메시지
                        detect_msg = DetectionInfo()
                        detect_msg.goal = self.goal
                        detect_msg.detected = self.detected
                        self.is_detected.publish(detect_msg)        # /is_detected 발행
                        

                        # 검출 정보 로깅
                       
                        self.get_logger().info(f'[{label_name}] 발견! 위치: x={pt_map.point.x:.2f}, y={pt_map.point.y:.2f}, 거리={z:.2f}m')

                        # 시각화
                        label = f"{label_name} ({pt_map.point.x:.1f}, {pt_map.point.y:.1f})"
                        cv2.rectangle(rgb_img, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        cv2.putText(rgb_img, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                      
                        self.get_logger().info('Published custom message!')
                    except Exception as e:
                        self.get_logger().warn(f'TF 변환 실패 ({label_name}): {e} {pt_camera.point.z}')
                        continue

            # 4. 결과 발행 및 성능 로그
            out_msg = self.bridge.cv2_to_imgmsg(rgb_img, encoding="bgr8")
            self.loss_item_view_pub.publish(out_msg)
            
            end_time = time.time()
            processing_ms = (end_time - start_time) * 1000
            if num_detected > 0:
                self.get_logger().debug(f'프레임 처리 완료: {num_detected}개 검출, 소요시간: {processing_ms:.1f}ms')

        except Exception as e:
            self.get_logger().error(f'콜백 실행 중 예외 발생: {e}')

def main():
    # 경로 확인 비판: 파일이 실제로 있는지 확인하는 로직을 넣으면 더 좋습니다.
    model_path = '/home/rokey/Desktop/Team_amatta/model/model2.pt'
    model = YOLO(model_path)
    
    rclpy.init()
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