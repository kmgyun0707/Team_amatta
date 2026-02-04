import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32MultiArray
import sys

class VisitedSpotPublisher(Node):
    def __init__(self):
        super().__init__('visited_spot_publisher')
        # /visited_spot 토픽 발행 설정
        self.publisher_ = self.create_publisher(Int32MultiArray, '/visited_spot', 10)
        print("Visited Spot Publisher Node Started.")
        print("-------------------------------------------------")
        print("사용자가 방문한 장소의 인덱스를 입력하세요.")
        print("예시: 0 1 5 (공백으로 구분)")
        print("종료하려면 Ctrl+C를 누르세요.")
        print("-------------------------------------------------")

    def run_console_input(self):
        try:
            while rclpy.ok():
                # 사용자 입력 받기
                user_input = input("\n방문한 장소 입력 > ")
                
                if not user_input.strip():
                    print("입력값이 없습니다. 다시 입력해주세요.")
                    continue

                try:
                    # 입력받은 문자열을 정수 리스트로 변환
                    data_list = [int(x) for x in user_input.split()]
                    
                    # 메시지 생성 및 데이터 할당
                    msg = Int32MultiArray()
                    msg.data = data_list
                    
                    # 토픽 발행
                    self.publisher_.publish(msg)
                    self.get_logger().info(f'Published Topic: {data_list}')
                    
                except ValueError:
                    print("오류: 숫자만 입력해주세요.")
                    
        except KeyboardInterrupt:
            print("\n종료합니다.")

def main(args=None):
    rclpy.init(args=args)
    
    publisher_node = VisitedSpotPublisher()
    
    # 별도 스핀 없이 콘솔 입력 루프 실행
    publisher_node.run_console_input()
    
    publisher_node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()