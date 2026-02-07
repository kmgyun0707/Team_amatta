import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
import cv2
import numpy as np
import time

class FakeCameraPublisher(Node):
    def __init__(self):
        super().__init__('fake_camera_publisher')
        
        # ---------------------------------------------------------
        # 1. 설정: 보낼 이미지 경로 & 토픽 이름
        # ---------------------------------------------------------
        # 테스트하고 싶은 이미지 경로를 입력하세요.
        img_path = '/home/rokey/rokey_ws/koalas.jpg' 
        
        # 통합 노드가 구독하는 토픽과 정확히 일치해야 합니다.
        topic_name = '/robot3/oakd/rgb/image_raw/compressed'
        
        # ---------------------------------------------------------
        # 2. 퍼블리셔 생성
        # ---------------------------------------------------------
        self.publisher_ = self.create_publisher(CompressedImage, topic_name, 10)
        self.timer = self.create_timer(0.1, self.publish_image) # 0.1초마다 발송 (10Hz)
        
        # ---------------------------------------------------------
        # 3. 이미지 로드 및 압축
        # ---------------------------------------------------------
        self.cv_image = cv2.imread(img_path)
        
        if self.cv_image is None:
            self.get_logger().error(f"이미지를 찾을 수 없습니다: {img_path}")
            self.get_logger().error("같은 폴더에 'test_image.jpg'를 넣거나 경로를 수정하세요.")
            exit()
            
        # 이미지를 jpg 형식으로 압축 (실제 카메라 데이터처럼 만듦)
        self.success, self.encoded_img = cv2.imencode('.jpg', self.cv_image)
        
        if not self.success:
            self.get_logger().error("이미지 인코딩(압축) 실패!")
            exit()

        print("="*50)
        print(f" [ Fake Camera Started ]")
        print(f" Image : {img_path}")
        print(f" Topic : {topic_name}")
        print("="*50)

    def publish_image(self):
        # 메시지 생성
        msg = CompressedImage()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.format = "jpeg"
        msg.data = np.array(self.encoded_img).tobytes() # 압축된 데이터 담기
        
        # 발행
        self.publisher_.publish(msg)
        # self.get_logger().info('Publishing Fake Image...')

def main(args=None):
    rclpy.init(args=args)
    node = FakeCameraPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()