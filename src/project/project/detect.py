import rclpy
import threading
from queue import Queue
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage, Image, CameraInfo
from cv_bridge import CvBridge
from ultralytics import YOLO
from pathlib import Path
import cv2
from geometry_msgs.msg import PointStamped
from tf2_ros import Buffer, TransformListener


class Detect(Node):
    def __init__(self, model):
        super().__init__("detect_yolo")

        #종료 
        self.should_shutdown = False

        self.bridge = CvBridge()

        #이미지 저장 큐 
        self.image_queue = Queue(maxsize=1)
        # #뎁스 저장 변수
        # self.latest_depth_img = None

        
        # #tf변환을 위한 버퍼 
        # self.tf_buffer = Buffer()
        # #tf리스너 
        # self.tf_listener = TransformListener(self.tf_buffer, self)



        #모델 
        self.model = model
        self.classNames = model.names if hasattr(model, 'names') else ['Object']
        
        
        
        
        
        self.intrinsics = None

        self.rgb_sub = self.create_subscription(CompressedImage, f'/robot3/oakd/rgb/image_raw/compressed', self.rgb_callback, 10)
        self.depth_sub = self.create_subscription(Image, f'/robot3/oakd/stereo/image_raw', self.depth_callback, 10)
        self.info_sub = self.create_subscription(CameraInfo, f'/robot3/oakd/rgb/camera_info', self.info_callback, 10)
        self.det_pub = self.create_publisher(Image, f'/robot3/detect_image', 10)
        
        
       
        self.thread = threading.Thread(target=self.detection_loop, daemon=True)
        self.thread.start()

        self.get_logger().info("self.init finish")

        


    def rgb_callback(self, msg):
            try:
                img = self.bridge.compressed_imgmsg_to_cv2(msg, desired_encoding='bgr8')
                if not self.image_queue.full():
                    self.image_queue.put(img)
            except Exception as e:
                self.get_logger().error(f"RGB 변환 실패: {e}")




    def depth_callback(self, msg):
        try:
            self.latest_depth_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')
        except Exception as e:
            self.get_logger().error(f"Depth 수신 실패: {e}")




    def info_callback(self, msg):
        """카메라 내부 파라미터(K) 추출"""
        if self.intrinsics is None:
            # K = [fx, 0, cx, 0, fy, cy, 0, 0, 1]
            self.intrinsics = {
                'fx': msg.k[0], 'fy': msg.k[4],
                'cx': msg.k[2], 'cy': msg.k[5],
                'frame_id': msg.header.frame_id
            }
            self.get_logger().info(f"Intrinsics Loaded: {self.intrinsics['frame_id']}")





    def detection_loop(self):
        self.get_logger().info("Detection Loop Thread Started")
        while rclpy.ok() and not self.should_shutdown:
            try:
                img = self.image_queue.get(timeout=0.5)
            except:
                # [DEBUG] 이미지 수신 여부 확인 (너무 잦으면 주석 처리)
                # self.get_logger().debug("Waiting for RGB image...")
                continue
            

            #카메라 정보 받을때까지 대기 
            if self.intrinsics is None:
                self.get_logger().warn("Waiting for CameraInfo...", throttle_duration_sec=5.0)
                continue
            
            #yolo 객체 판별 
            results = self.model.predict(img, verbose=False)
            

            #마지막 뎁스 데이터 받아오기 
            # depth_img = self.latest_depth_img.copy()
            # if depth_img is None:
            #     self.get_logger().warn("Depth image not received yet", throttle_duration_sec=2.0)

            # 검출 결과 요약
            if len(results) > 0 and len(results[0].boxes) > 0:
                self.get_logger().info(f"[YOLO] Detected {len(results[0].boxes)} objects")
            
      
            for r in results:
                for box in r.boxes:
                    #바운딩 박스 좌측 상단, 우측 하단 좌표 
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    #바운딩 박스 중심점 (뎁스 위치 값)
                    # u, v = int((x1 + x2) / 2), int((y1 + y2) / 2)

                    #클래스와 컨피던스정보 가져와 변수에 저장  (if사용으로 좀더 확실하게 동작하도록)
                    cls = int(box.cls[0]) if box.cls is not None else 0

                    conf = float(box.conf[0]) if box.conf is not None else 0.0

                    
                    # 1. 카메라 좌표계 (Optical Frame) 상의 X, Y, Z 계산
                    # z_c = self.get_robust_depth(depth_img, u, v) / 1000.0
                    # if z_c <= 0: continue

                    # x_c = (u - self.intrinsics['cx']) * z_c / self.intrinsics['fx']
                    # y_c = (v - self.intrinsics['cy']) * z_c / self.intrinsics['fy']
                    
                   
                    # pt_camera = PointStamped()
                    # pt_camera.header.frame_id = self.intrinsics['frame_id']
                    # pt_camera.header.stamp = self.get_clock().now().to_msg()
                    # pt_camera.point.x, pt_camera.point.y, pt_camera.point.z = x_c, y_c, z_c

                    # [DEBUG] 변환 전 카메라 좌표 출력
                    # self.get_logger().debug(f"[TF] Camera Coord: ({x_c:.2f}, {y_c:.2f}, {z_c:.2f})")

                    # pt_map = self.tf_buffer.transform(pt_camera, "map", timeout=rclpy.duration.Duration(seconds=0.1))
                    
                    # self.get_logger().info(f"✅ SUCCESS: [{self.classNames[int(box.cls[0])]}] "f"Map Target -> X:{pt_map.point.x:.2f}, Y:{pt_map.point.y:.2f}")



                    # if depth_img is not None:
                    #     cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                    #     if 0 <= cy < depth_img.shape[0] and 0 <= cx < depth_img.shape[1]:
                    #         dis = depth_img[cy, cx]
                    #         dis_str = f"{dis/1000.0:.2f}m" if dis > 0 else "Low Qual"


                    #라벨 저장 
                    label = f"{self.classNames[cls]} {conf:.2f}"# {dis_str}"
                    

                    #바운딩 박스 
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    self.get_logger().info(f"detect SUCCESS: [{self.classNames[int(box.cls[0])]}] ")



            # 결과 이미지 발행 로직 
            msg = self.bridge.cv2_to_imgmsg(img, encoding="bgr8")
            self.det_pub.publish(msg)




def main():
    model_path = "/home/rokey/rokey_ws/src/project/project/last_mk3.pt"

    model = YOLO(model_path, task='detect')
   
     

    rclpy.init()
    node = Detect(model)

    try:
        while rclpy.ok() and not node.should_shutdown:
            rclpy.spin_once(node, timeout_sec=0.05)
    except KeyboardInterrupt:
        node.get_logger().info("Shutdown requested via Ctrl+C.")
    finally:
        node.should_shutdown = True
        node.destroy_node()
        rclpy.shutdown()
        print("Shutdown complete.")



if __name__ == '__main__':
    main()
