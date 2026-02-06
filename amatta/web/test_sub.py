import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage # 둘 다 가져옴
from rclpy.qos import qos_profile_sensor_data

class MinimalSubscriber(Node):
    def __init__(self):
        super().__init__('minimal_subscriber')
        
        # 1. Raw 이미지 구독 시도 (Reliable 10)
        self.create_subscription(
            Image, 
            '/camera/color/image_raw', 
            self.listener_callback, 
            10
        )
        
        #/camera/color/image_raw
        # /robot3/oakd/rgb/image_raw'

        # 2. 혹시 모르니 Best Effort로도 구독 시도
        self.create_subscription(
            Image, 
            '/robot3/oakd/rgb/image_raw', 
            self.listener_callback_qos, 
            qos_profile_sensor_data
        )

    def listener_callback(self, msg):
        print(f"✅ [RELIABLE] 받음! 크기: {msg.width}x{msg.height}")

    def listener_callback_qos(self, msg):
        print(f"✅ [BEST_EFFORT] 받음! 크기: {msg.width}x{msg.height}")

def main():
    rclpy.init()
    node = MinimalSubscriber()
    print("테스트 시작... (이 메시지 뒤에 아무것도 안 뜨면 연결 문제)")
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()