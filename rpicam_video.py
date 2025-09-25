"""
Raspberry Pi Camera Video module using rpicam-vid with proper YUV handling
"""
import subprocess
import time
import logging
import threading
import queue

class RpiCameraVideo:
    def __init__(self, width=640, height=480, fps=30):
        self.width = width
        self.height = height
        self.fps = fps
        self.is_opened = False
        self.process = None
        self.frame_queue = queue.Queue(maxsize=2)
        self.reader_thread = None
        self.running = False

    def open(self):
        """Initialize rpicam-vid with YUV420 output"""
        try:
            # Simple rpicam-vid command for YUV420
            cmd = [
                'rpicam-vid',
                '--width', str(self.width),
                '--height', str(self.height),
                '--framerate', str(self.fps),
                '--timeout', '0',
                '--codec', 'yuv420',
                '--output', '-',
                '--nopreview'
            ]

            logging.info(f"Starting rpicam-vid: {' '.join(cmd)}")

            # Start rpicam-vid process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )

            # Wait for process to stabilize
            time.sleep(1)
            if self.process.poll() is not None:
                stderr_output = self.process.stderr.read().decode('utf-8', errors='ignore')
                logging.error(f"rpicam-vid failed: {stderr_output}")
                return False

            # Start frame reader thread
            self.running = True
            self.reader_thread = threading.Thread(target=self._frame_reader, daemon=True)
            self.reader_thread.start()

            self.is_opened = True
            logging.info(f"✓ RpiCameraVideo initialized: {self.width}x{self.height} @ {self.fps}fps")
            return True

        except Exception as e:
            logging.error(f"Failed to start rpicam-vid: {e}")
            return False

    def _frame_reader(self):
        """Read YUV420 frames and convert to BGR"""
        try:
            import cv2
            import numpy as np
        except ImportError:
            logging.error("OpenCV not available")
            return

        yuv_frame_size = self.width * self.height * 3 // 2
        logging.info(f"Frame reader started, expecting {yuv_frame_size} bytes per frame")

        buffer = bytearray()
        frames_read = 0

        while self.running and self.process and self.process.poll() is None:
            try:
                # Read chunk from process
                chunk = self.process.stdout.read(8192)  # 8KB chunks
                if not chunk:
                    time.sleep(0.001)
                    continue

                buffer.extend(chunk)

                # Process complete frames
                while len(buffer) >= yuv_frame_size:
                    # Extract one frame
                    yuv_data = buffer[:yuv_frame_size]
                    buffer = buffer[yuv_frame_size:]

                    # Convert YUV420 to BGR
                    bgr_frame = self._yuv420_to_bgr(yuv_data)
                    if bgr_frame is not None:
                        frames_read += 1

                        # Add to queue (drop old frames if full)
                        if self.frame_queue.full():
                            try:
                                self.frame_queue.get_nowait()
                            except queue.Empty:
                                pass

                        try:
                            self.frame_queue.put_nowait(bgr_frame)
                        except queue.Full:
                            pass

                        if frames_read % 100 == 0:
                            logging.info(f"Processed {frames_read} frames")

            except Exception as e:
                logging.error(f"Frame reader error: {e}")
                break

        logging.info(f"Frame reader stopped after {frames_read} frames")

    def _yuv420_to_bgr(self, yuv_data):
        """Convert YUV420 to BGR using OpenCV"""
        try:
            import cv2
            import numpy as np

            # Convert to numpy array
            yuv_array = np.frombuffer(yuv_data, dtype=np.uint8)

            # YUV420 layout: Y plane, U plane, V plane
            y_size = self.width * self.height
            uv_size = y_size // 4

            # Extract planes
            y = yuv_array[:y_size].reshape((self.height, self.width))
            u = yuv_array[y_size:y_size + uv_size].reshape((self.height // 2, self.width // 2))
            v = yuv_array[y_size + uv_size:].reshape((self.height // 2, self.width // 2))

            # Upsample chroma planes
            u_full = cv2.resize(u, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
            v_full = cv2.resize(v, (self.width, self.height), interpolation=cv2.INTER_LINEAR)

            # Stack YUV channels
            yuv_image = np.stack([y, u_full, v_full], axis=-1).astype(np.uint8)

            # Convert to BGR
            bgr_image = cv2.cvtColor(yuv_image, cv2.COLOR_YUV2BGR)
            return bgr_image

        except Exception as e:
            logging.error(f"YUV conversion error: {e}")
            return None

    def read(self):
        """Get latest frame from queue"""
        if not self.is_opened:
            return False, None

        try:
            frame = self.frame_queue.get(timeout=0.1)
            return True, frame
        except queue.Empty:
            return False, None
        except Exception as e:
            logging.error(f"Read error: {e}")
            return False, None

    def release(self):
        """Release camera resources"""
        self.is_opened = False
        self.running = False

        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=2)

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None

        logging.info("RpiCameraVideo released")

def create_video_camera(width=640, height=480, fps=30):
    """Create RpiCameraVideo instance"""
    return RpiCameraVideo(width, height, fps)