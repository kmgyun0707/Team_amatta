import rclpy                                     # ROS 2 Python 클라이언트 라이브러리
from rclpy.node import Node                      # Node 클래스
from sensor_msgs.msg import CompressedImage      # 압축 이미지 메시지 타입
from geometry_msgs.msg import Twist              # 로봇 속도 제어 메시지
from cv_bridge import CvBridge                   # OpenCV 변환 도구
from ultralytics import YOLO                     # YOLO 모델
import cv2                                       # OpenCV 라이브러리
import numpy as np                               # 수치 계산 라이브러리

class DetectionBrierScoreNode(Node):
    """
    ROS 2 노드: YOLO 모델의 Brier Score(확률적 정확도)를 실시간으로 평가하는 노드
    파일명: detection_brier_score.py
    """
    def __init__(self):
        super().__init__('detection_brier_score_node')
        
        # ---------------------------------------------------------
        # 1. 모델 로드 (경로 확인 필수)
        # ---------------------------------------------------------
        # 학습 완료된 YOLO 가중치 파일 로드
        self.model = YOLO('/home/rokey/rokey_ws/src/my_detection_bridge/models/best.pt')
        
        # ---------------------------------------------------------
        # 2. 통신 설정 (Subscriber & Publisher)
        # ---------------------------------------------------------
        self.bridge = CvBridge()
        
        # 카메라 구독: 대역폭 절약을 위해 CompressedImage 사용
        self.subscription = self.create_subscription(
            CompressedImage,
            '/robot3/oakd/rgb/image_raw/compressed',  # 팀원 토픽명
            self.image_callback,
            10)
            
        # 로봇 제어 발행: AMR을 움직이기 위한 Publisher
        self.cmd_vel_pub = self.create_publisher(Twist, '/robot3/cmd_vel', 10)
        
        # ---------------------------------------------------------
        # 3. 상태 관리 변수
        # ---------------------------------------------------------
        self.is_recording = False  # 'p'키: 데이터 기록 상태
        self.is_orbiting = False   # 'o'키: 주행 상태
        
        # [Brier Score용 데이터 저장소]
        # 단순 True/False가 아닌, 모델이 뱉은 'Confidence(0.0~1.0)' 값을 저장함
        self.confidence_history = [] 
        
        # ---------------------------------------------------------
        # 4. 주행 설정 (Orbit Motion)
        # ---------------------------------------------------------
        self.linear_speed = 0.15   # m/s
        self.angular_speed = 0.3   # rad/s (반경 약 0.5m)
        
        # ---------------------------------------------------------
        # 5. UI 안내 출력
        # ---------------------------------------------------------
        print("="*60)
        print(" [ Brier Score Evaluation Mode ] ")
        print(" 'o' : 주행 시작/중지 (Orbit Toggle)")
        print(" 'p' : 기록 시작/중지 (Record Toggle) -> 결과 출력")
        print(" 'i' : 비상 정지 (Emergency Stop)")
        print(" 'q' : 종료 (Quit)")
        print("="*60)
        self.get_logger().info("Ready. Press 'o' to move, 'p' to record.")

    def image_callback(self, msg):
        """
        카메라 이미지가 들어올 때마다 실행되는 콜백
        """
        try:
            # 1. 압축 해제 (Decoding)
            np_arr = np.frombuffer(msg.data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            self.get_logger().error(f'Decoding error: {e}')
            return

        # 2. YOLO 추론 (Inference)
        # Brier Score 계산을 위해 낮은 확신도도 일단 확인해야 하므로 conf를 낮게 잡거나 처리
        # 여기서는 일반적인 검출 기준인 0.5로 설정 (필요시 조절 가능)
        results = self.model.predict(source=frame, conf=0.5, verbose=False)
        
        # 3. 확신도(Confidence) 추출 로직
        current_conf = 0.0  # 기본값: 검출 실패 시 확신도 0
        
        if len(results[0].boxes) > 0:
            # 박스가 있으면 가장 높은 점수를 가져옴 (Tensor -> Float 변환)
            current_conf = float(results[0].boxes.conf[0])
            
        # 4. 주행 로직 ('o' 키)
        if self.is_orbiting:
            self.publish_orbit_cmd()

        # 5. 기록 로직 ('p' 키)
        if self.is_recording:
            # 매 프레임의 확신도 점수를 리스트에 저장
            self.confidence_history.append(current_conf)

        # 6. 시각화 (Visualization)
        annotated_frame = results[0].plot()
        
        # 상태 표시 UI
        rec_status = f"REC: {len(self.confidence_history)}" if self.is_recording else "REC: OFF"
        rec_color = (0, 0, 255) if self.is_recording else (200, 200, 200)
        
        move_status = "MOVE: ON" if self.is_orbiting else "MOVE: OFF"
        move_color = (0, 255, 0) if self.is_orbiting else (200, 200, 200)

        # 텍스트 그리기
        cv2.putText(annotated_frame, f"{rec_status} ('p')", (20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, rec_color, 2)
        cv2.putText(annotated_frame, f"{move_status} ('o')", (20, 80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, move_color, 2)
        
        # 현재 프레임의 확신도 표시
        cv2.putText(annotated_frame, f"Conf: {current_conf:.4f}", (20, 120), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        cv2.imshow("Brier Score Evaluation", annotated_frame)
        
        # 7. 키 입력 처리
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
        """로봇을 공전시키는 속도 명령"""
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

    def toggle_orbit(self):
        """주행 상태 토글"""
        self.is_orbiting = not self.is_orbiting
        if self.is_orbiting:
            self.get_logger().info(">>> MOTION START")
        else:
            self.stop_robot()
            self.get_logger().info(">>> MOTION PAUSED")

    def force_stop(self):
        """비상 정지"""
        self.is_orbiting = False
        self.stop_robot()
        self.get_logger().info("!!! EMERGENCY STOP !!!")

    def toggle_recording(self):
        """녹화 상태 토글 및 결과 계산 호출"""
        if not self.is_recording:
            self.is_recording = True
            self.confidence_history = [] # 데이터 초기화
            self.get_logger().info(">>> RECORDING START...")
        else:
            self.is_recording = False
            self.get_logger().info(">>> RECORDING STOP. Calculating Brier Score...")
            self.calculate_brier_score()

    def calculate_brier_score(self):
        """
        [핵심 기능] Brier Score 계산 및 리포트 출력
        """
        if not self.confidence_history:
            self.get_logger().warn("No data collected.")
            return

        total_frames = len(self.confidence_history)
        
        # 1. Brier Score 계산 로직
        # 시나리오 가정: 로봇이 물체 주위를 돌고 있으므로, 물체는 항상 화면에 있어야 함.
        # 즉, 실제 정답(Ground Truth)은 모든 프레임에서 1.0임.
        # 식: (예측확률 - 실제값)^2
        squared_errors = []
        for conf in self.confidence_history:
            ground_truth = 1.0  # 물체는 항상 존재함
            error = (conf - ground_truth) ** 2
            squared_errors.append(error)
            
        brier_score = sum(squared_errors) / total_frames

        # 2. 일반 인식률 계산 (참고용)
        # 확신도가 0.5(설정값) 이상인 경우만 검출 성공으로 간주
        detected_count = sum(1 for c in self.confidence_history if c > 0.0)
        detection_rate = (detected_count / total_frames) * 100

        # 3. 최종 리포트 출력
        print("\n" + "="*50)
        print(f" [ Brier Score Evaluation Report ]")
        print(f"-"*50)
        print(f" Total Frames   : {total_frames}")
        print(f" Detected Count : {detected_count} (Raw Detection)")
        print(f" Detection Rate : {detection_rate:.2f}%")
        print(f"-"*50)
        print(f" ★ Brier Score : {brier_score:.5f}")
        print(f"    - 해석: 0.0에 가까울수록 완벽한 예측")
        print(f"    - 해석: 0.25 이상이면 예측 능력이 떨어짐 (Guessing 수준)")
        print("="*50 + "\n")

def main(args=None):
    rclpy.init(args=args)
    node = DetectionBrierScoreNode()
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