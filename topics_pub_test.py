from my_robot_interfaces.msg import DetectionResult # DB 저장용
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from cv_bridge import CvBridge
import cv2




class Topic_test(Node):
    def __init__(self):
        super().__init__("topic_test")

        self.pub_server = self.create_publisher(DetectionResult, "/db_post", 1)
        self.timer_server = self.create_timer(1.0, self.server_data)

        self.bridge = CvBridge()

        self.get_logger().info('Publisher Node Started')
    


    def server_data(self):
        cv_Img = cv2.imread('/home/rokey/Desktop/amatta/Dooly.jpg')
        
        if cv_Img is None:
            self.get_logger().error('이미지를 읽을 수 없습니다! 경로를 확인하세요.')
            return # 에러 방지를 위해 여기서 중단

      
        lost_item = DetectionResult()
        lost_item.image =  self.bridge.cv2_to_imgmsg(cv_Img, encoding='bgr8')
        lost_item.class_name = "둘리"
        lost_item.ns = "robot3"
        lost_item.pose = PoseStamped()
        lost_item.pose.header.stamp = self.get_clock().now().to_msg()
        lost_item.pose.header.frame_id = "map"
        lost_item.pose.pose.position.x = 1.1
        lost_item.pose.pose.position.y = 1.4
        lost_item.pose.pose.position.z = 0.016

        self.pub_server.publish(lost_item)
        self.get_logger().info('Published server!')





def main():
    rclpy.init()
    node = Topic_test()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":   # ✅ 이거 없어서 바로 종료됐던 것
    main()



