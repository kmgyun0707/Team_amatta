import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage  # CompressedImage 타입 사용
from geometry_msgs.msg import Twist          # 로봇 이동 제어용
from cv_bridge import CvBridge
from ultralytics import YOLO
import cv2
import numpy as np

class DetectionTestNode(Node):
    def __init__(self):
        super().__init__('detection_test_node')
        
        # 1. 모델 로드 (경로 확인 필수!)
        # 예: /home/rokey/rokey_ws/src/my_detection_bridge/models/best.pt
        self.model = YOLO('/home/rokey/rokey_ws/src/my_detection_bridge/models/best.pt')
        
        # 2. 압축 이미지 구독 (팀원이 알려준 토픽명 적용)
        self.bridge = CvBridge()
        self.subscription = self.create_subscription(
            CompressedImage,
            '/robot3/oakd/rgb/image_raw/compressed',  
            self.image_callback,
            10)
            
        # 3. 로봇 주행 퍼블리셔 (Orbit 주행용)
        # 중요: 카메라 토픽에 /robot3가 있어서 cmd_vel도 /robot3가 붙을 가능성이 높음
        # 만약 로봇이 안 움직이면 터미널에서 'ros2 topic list'로 cmd_vel 토픽명을 확인 후 수정하세요.
        self.cmd_vel_pub = self.create_publisher(Twist, '/robot3/cmd_vel', 10)
        
        # 4. 테스트 상태 및 데이터 저장 변수
        self.test_active = False
        self.frames_data = []
        
        # --- [주행 설정] 공전(Orbit) 반경 조절 ---
        # 공식: 반경(Radius) = linear_speed / angular_speed
        # 아래 설정: 0.15 / 0.3 = 0.5m (50cm) 거리를 유지하며 돕니다.
        self.linear_speed = 0.15   # 전진 속도 (m/s)
        self.angular_speed = 0.3   # 회전 속도 (rad/s)
        
        self.get_logger().info("Ready. Press 's' to START Orbit & Test. Press 'q' to QUIT.")

    def image_callback(self, msg):
        # [핵심 1] CompressedImage 디코딩 (압축 해제)
        try:
            np_arr = np.frombuffer(msg.data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            self.get_logger().error(f'Decoding error: {e}')
            return

        # [핵심 2] YOLO 추론 (Confidence 상관없이 일단 수행)
        # stream=True 등을 쓰지 않고 한 장씩 정확히 처리
        results = self.model.predict(source=frame, conf=0.5, verbose=False)
        
        # 검출 여부 판단 (박스가 하나라도 있으면 True)
        target_found = len(results[0].boxes) > 0

        # [핵심 3] 테스트 중일 때: 데이터 기록 + 공전 주행 명령
        if self.test_active:
            self.frames_data.append(target_found)
            self.publish_orbit_cmd() # 계속 돌도록 명령 전송

        # 시각화 (화면 출력)
        annotated_frame = results[0].plot()
        status_text = "ORBITING..." if self.test_active else "STOPPED (Press 's')"
        color = (0, 0, 255) if self.test_active else (0, 255, 0)
        
        cv2.putText(annotated_frame, status_text, (20, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.imshow("AMR Orbit Detection Test", annotated_frame)
        
        # 키 입력 제어
        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            self.toggle_test()
        elif key == ord('q'):
            self.stop_robot()
            rclpy.shutdown()

    def publish_orbit_cmd(self):
        """로봇을 물체 중심으로 공전시키는 명령 (직진 + 회전)"""
        msg = Twist()
        msg.linear.x = self.linear_speed
        msg.angular.z = self.angular_speed
        self.cmd_vel_pub.publish(msg)

    def stop_robot(self):
        """로봇 정지"""
        msg = Twist()
        msg.linear.x = 0.0
        msg.angular.z = 0.0
        self.cmd_vel_pub.publish(msg)

    def toggle_test(self):
        if not self.test_active:
            # 테스트 시작
            self.test_active = True
            self.frames_data = [] # 데이터 초기화
            self.get_logger().info(">>> TEST START: Orbiting & Recording...")
        else:
            # 테스트 종료
            self.test_active = False
            self.stop_robot() # 로봇 멈춤
            self.get_logger().info(">>> TEST STOP: Analyzing results...")
            self.calculate_metrics()

    def calculate_metrics(self):
        if not self.frames_data:
            self.get_logger().warn("No data collected.")
            return

        total = len(self.frames_data)
        success = sum(self.frames_data)
        rate = (success / total) * 100
        
        # 연속 미검출(사각지대) 분석
        max_miss = 0
        curr_miss = 0
        for found in self.frames_data:
            if not found:
                curr_miss += 1
                max_miss = max(max_miss, curr_miss)
            else:
                curr_miss = 0
        
        # 결과 리포트 출력
        print("\n" + "="*40)
        print(f" [Orbit Performance Report] ")
        print(f" Topic        : /robot3/oakd/rgb/image_raw/compressed")
        print(f" Total Frames : {total}")
        print(f" Detected     : {success}")
        print(f" Accuracy     : {rate:.2f}%")
        print(f" Max Miss     : {max_miss} frames (Dead Zone Check)")
        print("="*40 + "\n")

def main(args=None):
    rclpy.init(args=args)
    node = DetectionTestNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop_robot() # 강제 종료 시에도 정지 명령 보냄
        node.destroy_node()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()