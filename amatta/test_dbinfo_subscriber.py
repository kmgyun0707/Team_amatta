#!/usr/bin/env python3
import rclpy
from rclpy.node import Node

from airport_guide_interfaces.msg import DbInfo


class DbInfoTestSubscriber(Node):
    def __init__(self):
        super().__init__('dbinfo_test_subscriber')

        self.subscription = self.create_subscription(
            DbInfo,
            '/is_registered',
            self.callback,
            10
        )

        self.get_logger().info('✅ DbInfo test subscriber started')
        self.get_logger().info('📡 Waiting for messages on /is_registered')

    def callback(self, msg: DbInfo):
        self.get_logger().info('================= DBinfo RECEIVED =================')
        self.get_logger().info(f'registered     : {msg.registered}')
        self.get_logger().info(f'item_id        : {msg.item_id}')
        self.get_logger().info(f'counter        : {msg.counter}')
        self.get_logger().info(f'visited_spots  : {list(msg.visited_spots)}')
        self.get_logger().info(f'gate_id        : {msg.gate_id}')
        self.get_logger().info('===================================================')


def main(args=None):
    rclpy.init(args=args)
    node = DbInfoTestSubscriber()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
