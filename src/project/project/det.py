"""

학습된 yolo11s 모델을 불러와 객체를 인식하고 바운딩박스를 만들어 
"/robot3/detect_image" 토픽으로 발행하는 프로그램 입니다.

"""

import rclpy
import threading
from queue import Queue
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage, Image, CameraInfo
from cv_bridge import CvBridge
from ultralytics import YOLO
from pathlib import Path
import cv2





# 클래스 선언
class Detect(Node):

    # 사용할 변수들,토픽들 선언
    def __init__(self, model):
        super().__init__("detect_yolo")

        self.should_shutdown = False

        self.bridge = CvBridge()

        # 이미지 저장 큐 
        self.image_queue = Queue(maxsize=1)
    


        # 모델 
        self.model = model
        self.classNames = model.names if hasattr(model, 'names') else ['Object']
        
        
        
        
        
        self.intrinsics = None

        self.rgb_sub = self.create_subscription(CompressedImage, f'/robot3/oakd/rgb/image_raw/compressed', self.rgb_callback, 10)
        self.det_pub = self.create_publisher(Image, f'/robot3/detect_image', 10)
        
        
       
        self.thread = threading.Thread(target=self.detection_loop, daemon=True)
        self.thread.start()

        self.get_logger().info("self.init finish")

        


    # rgb 카메라 데이터 구독 
    def rgb_callback(self, msg):
            try:
                img = self.bridge.compressed_imgmsg_to_cv2(msg, desired_encoding='bgr8')
                if not self.image_queue.full():
                    self.image_queue.put(img)
            except Exception as e:
                self.get_logger().error(f"RGB 변환 실패: {e}")




    # 객체 인식 후 바운딩박스와 라벨을 생성하여 이미지에 추가하고 /robot3/detect_image 토픽발행 , robot1의 
    def detection_loop(self):
        self.get_logger().info("Detection Loop Thread Started")
        while rclpy.ok() and not self.should_shutdown:
            try:
                img = self.image_queue.get(timeout=0.5)
            except:
                # [DEBUG] 이미지 수신 여부 확인 (너무 잦으면 주석 처리)
                # self.get_logger().debug("Waiting for RGB image...")
                continue
            

           
            
            #yolo 객체 판별 
            results = self.model.predict(img, verbose=False)
            

            # 검출 결과 요약
            if len(results) > 0 and len(results[0].boxes) > 0:
                self.get_logger().info(f"[YOLO] Detected {len(results[0].boxes)} objects")
            
      
            for r in results:
                for box in r.boxes:
                    #바운딩 박스 좌측 상단, 우측 하단 좌표 
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
        

                    #클래스와 컨피던스정보 가져와 변수에 저장  (if사용으로 좀더 확실하게 동작하도록)
                    cls = int(box.cls[0]) if box.cls is not None else 0

                    conf = float(box.conf[0]) if box.conf is not None else 0.0

                    
                   
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
    model_path = "/home/rokey/rokey_ws/src/project/project/best_real1.pt"

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
