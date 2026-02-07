import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from ultralytics import YOLO
import cv2
import numpy as np

class DetectionTestNode(Node):
    def __init__(self):
        super().__init__('detection_test_node')
        
        # 1. 모델 로드 (경로는 본인 환경에 맞게 수정 필수!)
        # 예: /home/rokey/rokey_ws/src/my_detection_bridge/models/best.pt
        self.model = YOLO('/home/rokey/rokey_ws/src/my_detection_bridge/models/best.pt')
        
        # 2. ROS 설정
        self.bridge = CvBridge()
        # AMR의 카메라 토픽 이름으로 변경해야 함 (예: /camera/image_raw, /usb_cam/image_raw)
        self.subscription = self.create_subscription(
            Image,
            '/image_raw',  
            self.image_callback,
            10)
        
        # 3. 테스트 상태 변수
        self.test_active = False
        self.frames_data = []
        
        self.get_logger().info("Ready for 360 Test. Press 's' on the popup window to START/STOP.")

    def image_callback(self, msg):
        try:
            # ROS 이미지 메시지 -> OpenCV 이미지 변환
            frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except Exception as e:
            self.get_logger().error(f'Conversion error: {e}')
            return

        # YOLO 추론
        results = self.model.predict(source=frame, conf=0.5, verbose=False)
        target_found = len(results[0].boxes) > 0

        # 테스트 중이면 데이터 저장
        if self.test_active:
            self.frames_data.append(target_found)

        # 시각화 (화면 출력)
        annotated_frame = results[0].plot()
        
        status_text = "RECORDING..." if self.test_active else "READY (Press 's')"
        color = (0, 0, 255) if self.test_active else (0, 255, 0)
        
        cv2.putText(annotated_frame, status_text, (20, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        
        cv2.imshow("AMR Object Detection Test", annotated_frame)
        
        # 키 입력 처리 ('s'로 시작/종료)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            self.toggle_test()
        elif key == ord('q'):
            rclpy.shutdown()

    def toggle_test(self):
        if not self.test_active:
            self.test_active = True
            self.frames_data = [] # 데이터 초기화
            self.get_logger().info(">>> TEST START: Recording data...")
        else:
            self.test_active = False
            self.get_logger().info(">>> TEST STOP: Analyzing results...")
            self.calculate_metrics()

    def calculate_metrics(self):
        if not self.frames_data:
            self.get_logger().warn("No data collected.")
            return

        total = len(self.frames_data)
        success = sum(self.frames_data)
        rate = (success / total) * 100
        
        # 연속 미검출 구간 계산
        max_miss = 0
        curr_miss = 0
        for found in self.frames_data:
            if not found:
                curr_miss += 1
                max_miss = max(max_miss, curr_miss)
            else:
                curr_miss = 0
        
        # 결과 로그 출력
        print("\n" + "="*40)
        print(f" [360 Rotation Test Result] ")
        print(f" Total Frames : {total}")
        print(f" Detected     : {success}")
        print(f" Accuracy     : {rate:.2f}%")
        print(f" Max Miss     : {max_miss} frames (Dead zone check)")
        print("="*40 + "\n")

def main(args=None):
    rclpy.init(args=args)
    node = DetectionTestNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        cv2.destroyAllWindows()
        # rclpy.shutdown()은 image_callback의 'q'에서 처리하거나 여기서 처리

if __name__ == '__main__':
    main()