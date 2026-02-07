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
        
        # 4. 상태 변수 (기록과 주행을 분리)
        self.is_recording = False  # 데이터 기록 여부 ('s'키)
        self.is_orbiting = False   # 로봇 주행 여부 ('o'키)
        self.frames_data = []
        
        # [주행 설정]
        self.linear_speed = 0.15
        self.angular_speed = 0.3
        
        print("="*50)
        print(" [Controls] ")
        print(" 'o' : Toggle Orbit Motion (Start/Stop Moving)")
        print(" 's' : Toggle Recording (Start/Stop Data Save)")
        print(" 'q' : Quit")
        print("="*50)
        self.get_logger().info("Node Started. Press 'o' to move, 's' to record.")

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

        # [변경 1] 주행 로직: is_orbiting 상태일 때만 명령 전송
        if self.is_orbiting:
            self.publish_orbit_cmd()

        # [변경 2] 기록 로직: is_recording 상태일 때만 데이터 저장
        if self.is_recording:
            self.frames_data.append(target_found)

        # 시각화 (화면 정보 표시 강화)
        annotated_frame = results[0].plot()
        
        # 상태 텍스트 표시
        # 녹화 상태 (REC)
        rec_text = "REC: ON" if self.is_recording else "REC: OFF"
        rec_color = (0, 0, 255) if self.is_recording else (200, 200, 200)
        
        # 주행 상태 (MOVE)
        move_text = "MOVE: ON" if self.is_orbiting else "MOVE: OFF"
        move_color = (0, 255, 0) if self.is_orbiting else (200, 200, 200)
        
        # 화면에 텍스트 그리기
        cv2.putText(annotated_frame, f"{rec_text} ('s')", (20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, rec_color, 2)
        cv2.putText(annotated_frame, f"{move_text} ('o')", (20, 80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, move_color, 2)
        
        cv2.imshow("AMR Orbit Detection Test", annotated_frame)
        
        # 키 입력 제어
        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            self.toggle_recording() # 녹화 토글
        elif key == ord('o'):
            self.toggle_orbit()     # 주행 토글
        elif key == ord('q'):
            self.stop_robot()
            rclpy.shutdown()

    def publish_orbit_cmd(self):
        msg = Twist()
        msg.linear.x = self.linear_speed
        msg.angular.z = self.angular_speed
        self.cmd_vel_pub.publish(msg)

    def stop_robot(self):
        msg = Twist()
        msg.linear.x = 0.0
        msg.angular.z = 0.0
        self.cmd_vel_pub.publish(msg)

    def toggle_orbit(self):
        """ 'o' 키를 눌렀을 때 실행 """
        self.is_orbiting = not self.is_orbiting
        if self.is_orbiting:
            self.get_logger().info(">>> MOTION START: Orbiting...")
        else:
            self.stop_robot() # 끄면 즉시 정지
            self.get_logger().info(">>> MOTION STOP: Robot halted.")

    def toggle_recording(self):
        """ 's' 키를 눌렀을 때 실행 """
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