import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from geometry_msgs.msg import Twist
from cv_bridge import CvBridge
from ultralytics import YOLO
import cv2
import numpy as np

class DetectionTestNode(Node):
    def __init__(self):
        super().__init__('detection_test_node')
        
        # 1. 모델 로드
        # 경로가 정확한지 다시 한번 확인해주세요!
        self.model = YOLO('/home/rokey/rokey_ws/src/my_detection_bridge/models/best.pt')
        
        # 2. 압축 이미지 구독
        self.bridge = CvBridge()
        self.subscription = self.create_subscription(
            CompressedImage,
            '/robot3/oakd/rgb/image_raw/compressed',  
            self.image_callback,
            10)
            
        # 3. 로봇 주행 퍼블리셔
        self.cmd_vel_pub = self.create_publisher(Twist, '/robot3/cmd_vel', 10)
        
        # 4. 상태 변수
        self.is_recording = False  # 녹화 상태 ('p'키)
        self.is_orbiting = False   # 주행 상태 ('o'키)
        self.frames_data = []
        
        # [주행 설정]
        self.linear_speed = 0.15
        self.angular_speed = 0.3
        
        print("="*50)
        print(" [Controls] ")
        print(" 'o' : 주행 시작/종료 (Orbit Toggle)")
        print(" 'p' : 녹화 시작/종료 (Record Toggle)")
        print(" 'i' : 즉시 정지 (Emergency Stop)")
        print(" 'q' : 프로그램 종료 (Quit)")
        print("="*50)
        self.get_logger().info("Ready. Press 'o' to move, 'p' to record, 'i' to stop.")

    def image_callback(self, msg):
        try:
            np_arr = np.frombuffer(msg.data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            self.get_logger().error(f'Decoding error: {e}')
            return

        # YOLO 추론
        results = self.model.predict(source=frame, conf=0.5, verbose=False)
        target_found = len(results[0].boxes) > 0

        # 주행 로직: is_orbiting 상태일 때만 명령 전송
        if self.is_orbiting:
            self.publish_orbit_cmd()

        # 기록 로직: is_recording 상태일 때만 데이터 저장
        if self.is_recording:
            self.frames_data.append(target_found)

        # --- 시각화 (화면 정보 표시) ---
        annotated_frame = results[0].plot()
        
        # 1. 녹화 상태 (REC) -> 'p' 키
        rec_text = "REC: ON" if self.is_recording else "REC: OFF"
        rec_color = (0, 0, 255) if self.is_recording else (200, 200, 200) # 빨강/회색
        
        # 2. 주행 상태 (MOVE) -> 'o' 키
        move_text = "MOVE: ON" if self.is_orbiting else "MOVE: OFF"
        move_color = (0, 255, 0) if self.is_orbiting else (200, 200, 200) # 초록/회색
        
        # 화면에 텍스트 그리기
        cv2.putText(annotated_frame, f"{rec_text} ('p')", (20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, rec_color, 2)
        cv2.putText(annotated_frame, f"{move_text} ('o')", (20, 80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, move_color, 2)
        cv2.putText(annotated_frame, "STOP ('i')", (20, 120), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        
        cv2.imshow("AMR Orbit Detection Test", annotated_frame)
        
        # --- 키 입력 제어 수정 ---
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('p'):      # [수정] 녹화 토글
            self.toggle_recording()
        elif key == ord('o'):    # [유지] 주행 토글
            self.toggle_orbit()
        elif key == ord('i'):    # [추가] 즉시 정지
            self.force_stop()
        elif key == ord('q'):    # [유지] 종료
            self.stop_robot()
            rclpy.shutdown()

    def publish_orbit_cmd(self):
        msg = Twist()
        msg.linear.x = self.linear_speed
        msg.angular.z = self.angular_speed
        self.cmd_vel_pub.publish(msg)

    def stop_robot(self):
        """로봇에 0 속도를 보내 멈추게 함"""
        msg = Twist()
        msg.linear.x = 0.0
        msg.angular.z = 0.0
        self.cmd_vel_pub.publish(msg)

    def toggle_orbit(self):
        """ 'o' 키: 주행 상태를 켜거나 끔 """
        self.is_orbiting = not self.is_orbiting
        if self.is_orbiting:
            self.get_logger().info(">>> MOTION START: Orbiting...")
        else:
            self.stop_robot()
            self.get_logger().info(">>> MOTION PAUSED.")

    def force_stop(self):
        """ 'i' 키: 무조건 멈춤 (녹화는 유지) """
        self.is_orbiting = False
        self.stop_robot()
        self.get_logger().info("!!! EMERGENCY STOP !!!")

    def toggle_recording(self):
        """ 'p' 키: 녹화 상태를 켜거나 끔 """
        if not self.is_recording:
            self.is_recording = True
            self.frames_data = [] # 데이터 초기화
            self.get_logger().info(">>> RECORDING START...")
        else:
            self.is_recording = False
            self.get_logger().info(">>> RECORDING STOP: Analyzing results...")
            self.calculate_metrics()

    def calculate_metrics(self):
        if not self.frames_data:
            self.get_logger().warn("No data collected during recording.")
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
        print(f" [Performance Report] ")
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
        node.stop_robot()
        node.destroy_node()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()