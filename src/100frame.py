import time
from ultralytics import YOLO

# 1. 모델 로드
model = YOLO('yolov8n.pt')  # 사용 중인 모델 경로

# 2. 100프레임 속도 체크
print("--- Inference Speed Test (100 Frames) ---")
dummy_input = "test_video.mp4"  # 또는 이미지 폴더
start_time = time.time()

# stream=True로 메모리 효율화, 100프레임만 제한하여 테스트
results = model.predict(source=dummy_input, stream=True, imgsz=640)
for i, r in enumerate(results):
    if i >= 100: break

end_time = time.time()
print(f"Total time for 100 frames: {end_time - start_time:.4f}s")
print(f"Average FPS: {100 / (end_time - start_time):.2f}")

# 3. mAP 50 및 50-95 비교
print("\n--- Validation Metrics (mAP) ---")
metrics = model.val(data='custom_data.yaml') # 학습 시 사용한 yaml
print(f"mAP@50: {metrics.box.map50:.4f}")
print(f"mAP@50-95: {metrics.box.map:.4f}")