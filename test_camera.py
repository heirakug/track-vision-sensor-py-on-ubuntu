#!/usr/bin/env python3
import cv2
import sys

def test_camera():
    """Test camera access"""
    print("Testing camera access...")

    # Try different camera indices
    for i in range(5):
        print(f"Trying camera index {i}...")
        cap = cv2.VideoCapture(i)

        if cap.isOpened():
            print(f"✓ Camera {i} opened successfully")
            ret, frame = cap.read()
            if ret:
                print(f"✓ Camera {i} can read frames - Shape: {frame.shape}")
                cap.release()
                return i
            else:
                print(f"✗ Camera {i} cannot read frames")
        else:
            print(f"✗ Camera {i} failed to open")

        cap.release()

    return None

if __name__ == "__main__":
    working_camera = test_camera()
    if working_camera is not None:
        print(f"\nWorking camera found at index: {working_camera}")
        sys.exit(0)
    else:
        print("\nNo working camera found")
        sys.exit(1)