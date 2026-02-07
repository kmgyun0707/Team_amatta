import rclpy                                     # ROS 2 Python 클라이언트
from rclpy.node import Node                      # Node 클래스
from sensor_msgs.msg import CompressedImage      # 압축 이미지 메시지
from geometry_msgs.msg import Twist              # 로봇 속도 제어
from cv_bridge import CvBridge                   # OpenCV 변환기
from ultralytics import YOLO                     # YOLO 모델
import cv2                                       # OpenCV
import numpy as np                               # 수치 계산

class IntegratedDetectionNode(Node):
    """
    [통합 노드]
    기능 1: AMR 공전 주행 (Orbit Motion)
    기능 2: YOLO 객체 인식 및 성능 평가
    평가 항목: 인식률(Accuracy), 사각지대(Max Miss), 브라이어 점수(Brier Score)
    """
    def __init__(self):
        super().__init__('integrated_detection_node')
        
        # ---------------------------------------------------------
        # 1. 모델 로드
        # ---------------------------------------------------------
        self.model = YOLO('/home/rokey/rokey_ws/001_my_best.pt')
        
        # ---------------------------------------------------------
        # 2. 통신 설정
        # ---------------------------------------------------------
        self.bridge = CvBridge()
        
        # 카메라 구독
        self.subscription = self.create_subscription(
            CompressedImage,
            '/robot3/oakd/rgb/image_raw/compressed',  
            self.image_callback,
            10)
            
        # 로봇 제어 발행
        self.cmd_vel_pub = self.create_publisher(Twist, '/robot3/cmd_vel', 10)
        
        # ---------------------------------------------------------
        # 3. 상태 변수
        # ---------------------------------------------------------
        self.is_recording = False  # 'p'키
        self.is_orbiting = False   # 'o'키
        
        # [데이터 저장소]
        # 확신도(Confidence, 0.0~1.0)를 저장하면 모든 지표 계산 가능
        self.confidence_history = [] 
        
        # ---------------------------------------------------------
        # 4. 주행 설정
        # ---------------------------------------------------------
        self.linear_speed = 0.15   # m/s
        self.angular_speed = 0.3   # rad/s
        
        # ---------------------------------------------------------
        # 5. UI 안내
        # ---------------------------------------------------------
        print("="*60)
        print(" [ Integrated Performance Test ] ")
        print(" 'o' : 주행 (Orbit) ON/OFF")
        print(" 'p' : 녹화 (Record) ON/OFF -> 결과 리포트 출력")
        print(" 'i' : 비상 정지 (Emergency Stop)")
        print(" 'q' : 종료 (Quit)")
        print("="*60)
        self.get_logger().info("Ready. Press 'o' to move, 'p' to record.")

    def image_callback(self, msg):
        try:
            # 이미지 디코딩
            np_arr = np.frombuffer(msg.data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            self.get_logger().error(f'Decoding error: {e}')
            return

        # ---------------------------------------------------------
        # A. YOLO 추론
        # ---------------------------------------------------------
        # conf=0.5: 확신도 0.5 이상만 박스로 인정
        results = self.model.predict(source=frame, conf=0.5, verbose=False)
        
        # 현재 프레임의 확신도 추출 (없으면 0.0)
        current_conf = 0.0
        if len(results[0].boxes) > 0:
            current_conf = float(results[0].boxes.conf[0])

        # ---------------------------------------------------------
        # B. 로직 처리
        # ---------------------------------------------------------
        # 1. 주행: 켜져 있으면 계속 명령 전송
        if self.is_orbiting:
            self.publish_orbit_cmd()

        # 2. 기록: 켜져 있으면 확신도 저장
        if self.is_recording:
            self.confidence_history.append(current_conf)

        # ---------------------------------------------------------
        # C. 시각화 (HUD)
        # ---------------------------------------------------------
        annotated_frame = results[0].plot()
        
        # 상태 텍스트 색상 설정
        rec_text = f"REC: {len(self.confidence_history)}" if self.is_recording else "REC: OFF"
        rec_color = (0, 0, 255) if self.is_recording else (200, 200, 200)
        
        move_text = "MOVE: ON" if self.is_orbiting else "MOVE: OFF"
        move_color = (0, 255, 0) if self.is_orbiting else (200, 200, 200)

        # 화면에 정보 표시
        cv2.putText(annotated_frame, f"{rec_text} ('p')", (20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, rec_color, 2)
        cv2.putText(annotated_frame, f"{move_text} ('o')", (20, 80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, move_color, 2)
        cv2.putText(annotated_frame, f"Conf: {current_conf:.2f}", (20, 120), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(annotated_frame, "STOP ('i')", (20, 160), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

        cv2.imshow("Integrated Test", annotated_frame)
        
        # ---------------------------------------------------------
        # D. 키 입력 제어
        # ---------------------------------------------------------
        key = cv2.waitKey(1) & 0xFF
        if key == ord('p'):
            self.toggle_recording()
        elif key == ord('o'):
            self.toggle_orbit()
        elif key == ord('i'):
            self.force_stop()
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
        self.is_orbiting = not self.is_orbiting
        if self.is_orbiting:
            self.get_logger().info(">>> MOTION START")
        else:
            self.stop_robot()
            self.get_logger().info(">>> MOTION PAUSED")

    def force_stop(self):
        self.is_orbiting = False
        self.stop_robot()
        self.get_logger().info("!!! EMERGENCY STOP !!!")

    def toggle_recording(self):
        if not self.is_recording:
            self.is_recording = True
            self.confidence_history = [] # 데이터 초기화
            self.get_logger().info(">>> RECORDING START...")
        else:
            self.is_recording = False
            self.get_logger().info(">>> RECORDING STOP. Calculating Metrics...")
            self.calculate_integrated_metrics()

    def calculate_integrated_metrics(self):
        """
        [통합 성능 계산 함수]
        1. Accuracy (인식률)
        2. Max Consecutive Miss (사각지대 안정성)
        3. Brier Score (확률적 정확도)
        """
        if not self.confidence_history:
            self.get_logger().warn("No data collected.")
            return

        data = self.confidence_history
        total_frames = len(data)
        
        # 1. 인식률 계산 (Confidence가 0보다 크면 성공)
        detected_count = sum(1 for c in data if c > 0.0)
        accuracy = (detected_count / total_frames) * 100
        
        # 2. 연속 미검출(사각지대) 계산
        max_miss = 0
        curr_miss = 0
        for c in data:
            if c == 0.0:  # 미검출
                curr_miss += 1
                max_miss = max(max_miss, curr_miss)
            else:         # 검출
                curr_miss = 0

        # 3. Brier Score 계산
        # Ground Truth = 1.0 (항상 물체가 있다고 가정)
        # 식: (예측값 - 1.0)^2 의 평균
        squared_errors = [(c - 1.0) ** 2 for c in data]
        brier_score = sum(squared_errors) / total_frames

        # ---------------------------------------------------------
        # 최종 리포트 출력
        # ---------------------------------------------------------
        print("\n" + "="*50)
        print(f" [ Final Performance Report ]")
        print(f"-"*50)
        print(f" 1. Basic Metrics")
        print(f"    - Total Frames : {total_frames}")
        print(f"    - Detected     : {detected_count}")
        print(f"    - Accuracy     : {accuracy:.2f}%")
        print(f"")
        print(f" 2. Stability (Dead Zone)")
        print(f"    - Max Miss Streak : {max_miss} frames")
        print(f"      (값이 클수록 특정 각도에서 인식이 끊김)")
        print(f"")
        print(f" 3. Reliability (Probabilistic)")
        print(f"    - Brier Score     : {brier_score:.5f}")
        print(f"      (0.00: 완벽, >0.25: 예측력 낮음)")
        print("="*50 + "\n")

def main(args=None):
    rclpy.init(args=args)
    node = IntegratedDetectionNode()
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