import rclpy
from rclpy.node import Node
from airport_guide_interfaces.msg import DbInfo
from std_msgs.msg import Int32MultiArray

class DbPublisher(Node):
    def __init__(self):
        super().__init__('db_publisher')
        # /visited_spot 토픽 발행 설정
        self.publisher_ = self.create_publisher(DbInfo, '/is_registered', 10)
        print("Detection Publisher Node Started.")
        print("-------------------------------------------------")
        print("분실물이 DB에 있는지 여부를 입력하세요 (1: True / 0: False)")
        print("-------------------------------------------------")

    def run_console_input(self):
        try:
            while rclpy.ok():
                user_input = input("\n탐지 여부(1 또는 0) > ").strip()
                
                # 3. 입력값에 따른 Bool 메시지 생성 로직
                msg = DbInfo()
                if user_input == '1':
                    msg.registered = True
                elif user_input == '0':
                    msg.registered = False

                    user_input = input("\n방문한 장소 입력 > ")
                    # 입력받은 문자열을 정수 리스트로 변환
                    data_list = [int(x) for x in user_input.split()]
                    
                    # 메시지 생성 및 데이터 할당
                    msg = Int32MultiArray()
                    msg.visited_spots = data_list
                    
                    user_input_gate = input("\n방문할 게이트 입력 > ")
                    msg.gate_id = int(user_input_gate)
                else:
                    print("잘못된 입력입니다. 1 또는 0을 입력하세요.")
                    continue
                
                # 토픽 발행
                self.publisher_.publish(msg)
                self.get_logger().info(f'Published /is_registered: {msg.registered}')
                    
        except KeyboardInterrupt:
            print("\n종료합니다.")

def main(args=None):
    rclpy.init(args=args)
    
    publisher_node = DbPublisher()
    
    # 별도 스핀 없이 콘솔 입력 루프 실행
    publisher_node.run_console_input()
    
    publisher_node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()