import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist  # 로봇 제어 메시지 추가
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
        
        # 2. 카메라 구독 (Subscription)
        self.bridge = CvBridge()
        self.subscription = self.create_subscription(
            Image,
            '/image_raw',   # 실제 로봇 카메라 토픽 확인 (예: /camera/image_raw)
            self.image_callback,
            10)
            
        # 3. 로봇 구동 퍼블리셔 (Publisher) 추가
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # 4. 테스트 상태 변수
        self.test_active = False
        self.frames_data = []
        
        # --- [중요] 주행 설정 값 (반경 조절) ---
        # 원의 반경(Radius) = linear_x / angular_z
        # 예: 0.15 / 0.3 = 0.5m 거리 유지하며 회전
        self.linear_speed = 0.15  # m/s (직진 속도)
        self.angular_speed = 0.3  # rad/s (회전 속도)
        
        self.get_logger().info("Ready. Press 's' to START (Orbit & Record). Press 'q' to QUIT.")

    def image_callback(self, msg):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except Exception as e:
            self.get_logger().error(f'Conversion error: {e}')
            return

        # YOLO 추론
        results = self.model.predict(source=frame, conf=0.5, verbose=False)
        target_found = len(results[0].boxes) > 0

        # 테스트 중일 때만 데이터 저장 및 로봇 주행 유지
        if self.test_active:
            self.frames_data.append(target_found)
            self.publish_orbit_cmd() # 지속적으로 주행 명령 전송

        # 시각화
        annotated_frame = results[0].plot()
        status_text = "ORBITING..." if self.test_active else "STOPPED (Press 's')"
        color = (0, 0, 255) if self.test_active else (0, 255, 0)
        
        cv2.putText(annotated_frame, status_text, (20, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.imshow("AMR Orbit Detection Test", annotated_frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            self.toggle_test()
        elif key == ord('q'):
            self.stop_robot() # 종료 시 로봇 정지
            rclpy.shutdown()

    def publish_orbit_cmd(self):
        """로봇을 원형으로 움직이게 하는 명령"""
        msg = Twist()
        msg.linear.x = self.linear_speed
        msg.angular.z = self.angular_speed
        self.cmd_vel_pub.publish(msg)

    def stop_robot(self):
        """로봇 정지 명령"""
        msg = Twist()
        msg.linear.x = 0.0
        msg.angular.z = 0.0
        self.cmd_vel_pub.publish(msg)

    def toggle_test(self):
        if not self.test_active:
            # 시작 로직
            self.test_active = True
            self.frames_data = []
            self.get_logger().info(">>> TEST START: Orbiting & Recording...")
        else:
            # 종료 로직
            self.test_active = False
            self.stop_robot() # 로봇 멈춤
            self.get_logger().info(">>> TEST STOP: Robot Stopped.")
            self.calculate_metrics()

    def calculate_metrics(self):
        if not self.frames_data:
            self.get_logger().warn("No data collected.")
            return

        total = len(self.frames_data)
        success = sum(self.frames_data)
        rate = (success / total) * 100
        
        max_miss = 0
        curr_miss = 0
        for found in self.frames_data:
            if not found:
                curr_miss += 1
                max_miss = max(max_miss, curr_miss)
            else:
                curr_miss = 0
        
        print("\n" + "="*40)
        print(f" [Orbit Performance Report] ")
        print(f" Total Frames : {total}")
        print(f" Detected     : {success}")
        print(f" Accuracy     : {rate:.2f}%")
        print(f" Max Miss     : {max_miss} frames")
        print("="*40 + "\n")

def main(args=None):
    rclpy.init(args=args)
    node = DetectionTestNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop_robot() # 강제 종료 시에도 멈춤 보장
        node.destroy_node()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()