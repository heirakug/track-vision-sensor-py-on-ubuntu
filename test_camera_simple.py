#!/usr/bin/env python3
import cv2
import time

def test_camera():
    print("Testing camera configurations...")

    # 試行するカメラ設定
    configs = [
        {"index": 0, "name": "Default camera 0"},
        {"index": 1, "name": "Camera 1"},
        {"pipeline": "libcamerasrc ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! appsink", "name": "libcamera GStreamer"},
        {"pipeline": f"v4l2src device=/dev/video0 ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! appsink", "name": "V4L2 /dev/video0"},
    ]

    for config in configs:
        print(f"\nTesting: {config['name']}")

        try:
            if 'pipeline' in config:
                cap = cv2.VideoCapture(config['pipeline'], cv2.CAP_GSTREAMER)
            else:
                cap = cv2.VideoCapture(config['index'])

            if not cap.isOpened():
                print(f"  ❌ Failed to open")
                continue

            # フレーム読み取りテスト
            ret, frame = cap.read()
            if not ret:
                print(f"  ❌ Failed to read frame")
                cap.release()
                continue

            print(f"  ✅ Success! Frame shape: {frame.shape}")

            # フレームが真っ黒でないかチェック
            mean_intensity = frame.mean()
            print(f"  📊 Mean intensity: {mean_intensity:.2f}")

            if mean_intensity < 5:
                print(f"  ⚠️  Frame appears to be mostly black")
            elif mean_intensity > 250:
                print(f"  ⚠️  Frame appears to be mostly white/green")
            else:
                print(f"  ✅ Frame appears to have proper content")

            # テスト画像を保存
            filename = f"test_frame_{config['name'].replace(' ', '_').replace('/', '_')}.jpg"
            cv2.imwrite(filename, frame)
            print(f"  💾 Saved test frame: {filename}")

            cap.release()

        except Exception as e:
            print(f"  ❌ Error: {e}")

if __name__ == "__main__":
    test_camera()