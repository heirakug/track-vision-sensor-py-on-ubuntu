#!/usr/bin/env python3
import cv2
import subprocess
import sys

def test_libcamera():
    """Test libcamera integration with OpenCV"""
    print("Testing libcamera integration...")

    # Try libcamera with different backends
    backends = [
        "libcamera",
        "gstreamer",
        "v4l2"
    ]

    gstreamer_pipelines = [
        "libcamerasrc ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! appsink",
        "v4l2src device=/dev/video0 ! video/x-raw,width=640,height=480 ! videoconvert ! appsink"
    ]

    # Test GStreamer pipelines
    for i, pipeline in enumerate(gstreamer_pipelines):
        print(f"\nTrying GStreamer pipeline {i+1}: {pipeline}")
        try:
            cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    print(f"✓ GStreamer pipeline {i+1} works - Frame shape: {frame.shape}")
                    cap.release()
                    return pipeline
                else:
                    print(f"✗ GStreamer pipeline {i+1} opened but cannot read frames")
            else:
                print(f"✗ GStreamer pipeline {i+1} failed to open")
            cap.release()
        except Exception as e:
            print(f"✗ GStreamer pipeline {i+1} error: {e}")

    return None

if __name__ == "__main__":
    working_pipeline = test_libcamera()
    if working_pipeline:
        print(f"\nWorking pipeline found: {working_pipeline}")
        sys.exit(0)
    else:
        print("\nNo working camera pipeline found")
        sys.exit(1)