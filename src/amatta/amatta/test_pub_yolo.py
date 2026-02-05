import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
import sys

class YoloPublisher(Node):
    def __init__(self):
        super().__init__('yolo_publisher')
        # /visited_spot 토픽 발행 설정
        self.publisher_ = self.create_publisher(Bool, '/is_detected', 10)
        print("Detection Publisher Node Started.")
        print("-------------------------------------------------")
        print("탐지 여부를 입력하세요 (1: True / 0: False)")
        print("-------------------------------------------------")

    def run_console_input(self):
        try:
            while rclpy.ok():
                user_input = input("\n탐지 여부(1 또는 0) > ").strip()
                
                # 3. 입력값에 따른 Bool 메시지 생성 로직
                msg = Bool()
                if user_input == '1':
                    msg.data = True
                elif user_input == '0':
                    msg.data = False
                else:
                    print("잘못된 입력입니다. 1 또는 0을 입력하세요.")
                    continue
                
                # 토픽 발행
                self.publisher_.publish(msg)
                self.get_logger().info(f'Published /is_detected: {msg.data}')
                    
        except KeyboardInterrupt:
            print("\n종료합니다.")

def main(args=None):
    rclpy.init(args=args)
    
    publisher_node = YoloPublisher()
    
    # 별도 스핀 없이 콘솔 입력 루프 실행
    publisher_node.run_console_input()
    
    publisher_node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()