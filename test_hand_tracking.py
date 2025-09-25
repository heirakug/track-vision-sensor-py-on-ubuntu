#!/usr/bin/env python3
"""
ハンドトラッキング機能のテストスクリプト
"""

import cv2
import logging
import time
import mediapipe as mp
from rpicamera import create_camera

logging.basicConfig(level=logging.INFO)

def test_hand_tracking_basic():
    """基本的なハンドトラッキングテスト"""

    print("=== Basic Hand Tracking Test ===")

    # MediaPipe初期化
    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5
    )

    # カメラ初期化
    camera = create_camera(640, 480, 30, streaming=True)

    if not camera.open():
        print("❌ Failed to open camera")
        return

    print("✅ Camera opened - testing hand detection...")
    print("Put your hand in front of the camera")

    detection_count = 0
    frame_count = 0
    start_time = time.time()

    try:
        for i in range(30):  # 30フレームテスト
            ret, frame = camera.read()
            if not ret:
                print(f"❌ Frame {i+1}: Failed to read")
                continue

            frame_count += 1

            # BGR → RGB変換（MediaPipe用）
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 手検出実行
            results = hands.process(rgb_frame)

            # 結果チェック
            if results.multi_hand_landmarks:
                detection_count += 1
                num_hands = len(results.multi_hand_landmarks)
                print(f"✅ Frame {i+1}: {num_hands} hand(s) detected")

                # 詳細情報
                for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    palm_center = hand_landmarks.landmark[9]  # 手のひら中心
                    print(f"   Hand {hand_idx}: palm at ({palm_center.x:.3f}, {palm_center.y:.3f})")

            else:
                print(f"⚪ Frame {i+1}: No hands detected")

            time.sleep(0.1)  # 100ms間隔

    except KeyboardInterrupt:
        print("\nTest interrupted by user")

    elapsed_time = time.time() - start_time
    detection_rate = (detection_count / frame_count) * 100 if frame_count > 0 else 0

    print(f"\n=== Test Results ===")
    print(f"Total frames: {frame_count}")
    print(f"Frames with hands detected: {detection_count}")
    print(f"Detection rate: {detection_rate:.1f}%")
    print(f"Average FPS: {frame_count / elapsed_time:.1f}")

    if detection_rate > 0:
        print("✅ Hand detection is working")
    else:
        print("❌ No hands detected - possible issues:")
        print("  - Insufficient lighting")
        print("  - Hand not in frame")
        print("  - MediaPipe configuration issue")
        print("  - Camera color format issue")

    camera.release()
    hands.close()

def test_main_py_integration():
    """main.pyの統合テスト"""

    print("\n=== Main.py Integration Test ===")

    try:
        from main import MultiModalTracker

        tracker = MultiModalTracker(
            enable_hands=True,
            enable_face=False,
            enable_pose=False,
            headless=True
        )

        print("✅ MultiModalTracker initialized")

        # カメラチェック
        if tracker.cap and tracker.cap.isOpened():
            print("✅ Camera is open")

            # 数フレームテスト
            for i in range(5):
                ret, frame = tracker.cap.read()
                if ret:
                    print(f"✅ Frame {i+1}: {frame.shape}")

                    # RGB変換
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                    # 手検出テスト
                    if hasattr(tracker, 'hands'):
                        results = tracker.hands.process(rgb_frame)
                        if results.multi_hand_landmarks:
                            print(f"   → {len(results.multi_hand_landmarks)} hand(s) detected in main.py")
                        else:
                            print("   → No hands detected in main.py")
                    else:
                        print("   → No hands module found")
                else:
                    print(f"❌ Frame {i+1}: Failed")

                time.sleep(0.2)

        # クリーンアップ
        if hasattr(tracker, 'cap') and tracker.cap:
            tracker.cap.release()

    except Exception as e:
        print(f"❌ Main.py test failed: {e}")
        import traceback
        traceback.print_exc()

def test_performance_analysis():
    """パフォーマンス分析"""

    print("\n=== Performance Analysis ===")

    # MediaPipe設定の比較
    configs = [
        {"name": "Default", "detection": 0.7, "tracking": 0.5},
        {"name": "Sensitive", "detection": 0.5, "tracking": 0.3},
        {"name": "Fast", "detection": 0.8, "tracking": 0.7},
    ]

    camera = create_camera(640, 480, 30, streaming=False)
    if not camera.open():
        print("❌ Camera failed")
        return

    for config in configs:
        print(f"\nTesting {config['name']} config...")

        mp_hands = mp.solutions.hands
        hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=config["detection"],
            min_tracking_confidence=config["tracking"]
        )

        detection_times = []
        detection_count = 0

        for i in range(10):
            ret, frame = camera.read()
            if ret:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                start_time = time.time()
                results = hands.process(rgb_frame)
                process_time = time.time() - start_time

                detection_times.append(process_time)

                if results.multi_hand_landmarks:
                    detection_count += 1

        avg_time = sum(detection_times) / len(detection_times) if detection_times else 0
        print(f"  Average processing time: {avg_time*1000:.1f}ms")
        print(f"  Detection rate: {detection_count}/10")
        print(f"  Estimated FPS: {1/avg_time:.1f}" if avg_time > 0 else "N/A")

        hands.close()

    camera.release()

if __name__ == "__main__":
    test_hand_tracking_basic()
    test_main_py_integration()
    test_performance_analysis()