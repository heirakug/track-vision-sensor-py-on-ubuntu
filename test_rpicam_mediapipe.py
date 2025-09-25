#!/usr/bin/env python3
import subprocess
import tempfile
import time
import cv2
import os
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)

def test_rpicam_integration():
    """rpicamで画像を取得してMediaPipeで処理するテスト"""

    temp_dir = Path("camera_test_output/rpicam_stream")
    temp_dir.mkdir(exist_ok=True)

    logging.info("=== rpicam + MediaPipe integration test ===")

    try:
        # rpicam-jpegでリアルタイム画像取得をシミュレート
        for i in range(5):
            output_file = temp_dir / f"frame_{i:03d}.jpg"

            # rpicam-jpegで1フレーム取得
            cmd = [
                "rpicam-jpeg",
                "--output", str(output_file),
                "--width", "640",
                "--height", "480",
                "--timeout", "100",  # 100ms
                "--nopreview"
            ]

            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True)
            capture_time = time.time() - start_time

            if result.returncode == 0 and output_file.exists():
                # OpenCVで画像を読み込み
                frame = cv2.imread(str(output_file))
                if frame is not None:
                    logging.info(f"Frame {i+1}: Captured in {capture_time:.3f}s, Shape={frame.shape}, Mean={frame.mean():.2f}")

                    # ここでMediaPipe処理をシミュレート
                    # 実際には手検出などを行う
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    logging.info(f"  Converted to RGB: {frame_rgb.shape}")

                else:
                    logging.error(f"Failed to load image: {output_file}")
            else:
                logging.error(f"rpicam-jpeg failed: {result.stderr}")

        # バックグラウンドストリーミングテスト
        logging.info("\n=== Testing background streaming ===")

        # rpicam-vidでストリーミング開始（バックグラウンド）
        stream_file = temp_dir / "stream.h264"
        stream_cmd = [
            "rpicam-vid",
            "--output", str(stream_file),
            "--width", "640",
            "--height", "480",
            "--timeout", "3000",  # 3秒
            "--nopreview"
        ]

        logging.info("Starting background video stream...")
        stream_process = subprocess.Popen(stream_cmd)

        # 少し待ってプロセス状況確認
        time.sleep(1)
        if stream_process.poll() is None:
            logging.info("✅ Background streaming running")
        else:
            logging.error("❌ Background streaming failed")

        # ストリーミング終了を待つ
        stream_process.wait()

        if stream_file.exists():
            file_size = stream_file.stat().st_size
            logging.info(f"✅ Stream file created: {file_size} bytes")

            # ffmpegで個別フレームに分割
            extract_cmd = [
                "ffmpeg", "-i", str(stream_file),
                "-vf", "fps=1",  # 1fps で抽出
                str(temp_dir / "extracted_%03d.jpg"),
                "-y"  # 上書き
            ]

            result = subprocess.run(extract_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                extracted_files = list(temp_dir.glob("extracted_*.jpg"))
                logging.info(f"✅ Extracted {len(extracted_files)} frames from video")

                # 最初の抽出フレームをテスト
                if extracted_files:
                    test_frame = cv2.imread(str(extracted_files[0]))
                    if test_frame is not None:
                        logging.info(f"Test frame: {test_frame.shape}, Mean={test_frame.mean():.2f}")
                        logging.info("✅ Video->Image->OpenCV pipeline working")
            else:
                logging.error(f"ffmpeg extraction failed: {result.stderr}")

        else:
            logging.error("❌ No stream file created")

    except Exception as e:
        logging.error(f"Test failed: {e}")

    finally:
        # クリーンアップ
        logging.info(f"Test files in: {temp_dir}")

if __name__ == "__main__":
    test_rpicam_integration()