import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class SimplePublisher(Node):

    def __init__(self):
        super().__init__('simple_publisher')
        self.pub = self.create_publisher(String, 'greetings', 10)    
        timer_period = 1.0
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.msg_list = ['삐', '뽀']
        self.count = 0

    def timer_callback(self): 
        msg = String(data=self.msg_list[self.count%2])
        self.pub.publish(msg)
        self.get_logger().warn(msg.data)
        self.count += 1

def main():
    rclpy.init()
    node = SimplePublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

# def main():
#     print('Hi from turtlebot4_beep.')

if __name__ == '__main__':
    main()


