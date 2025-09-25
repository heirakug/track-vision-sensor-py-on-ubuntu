"""
Raspberry Pi Camera module - Simple OpenCV implementation
"""
import subprocess
import time
import logging

class RpiCamera:
    def __init__(self, width=640, height=480, fps=30, streaming=False):
        self.width = width
        self.height = height
        self.fps = fps
        self.streaming = streaming
        self.is_opened = False
        self.cap = None

    def open(self):
        """Initialize camera using OpenCV VideoCapture"""
        try:
            # Import cv2 only when needed
            import cv2

            # Try OpenCV VideoCapture
            self.cap = cv2.VideoCapture(0)

            if self.cap.isOpened():
                # Set camera properties
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self.cap.set(cv2.CAP_PROP_FPS, self.fps)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                # Test frame read
                ret, test_frame = self.cap.read()
                if ret and test_frame is not None:
                    self.is_opened = True
                    logging.info(f"✓ RpiCamera (OpenCV) initialized: {self.width}x{self.height} @ {self.fps}fps")
                    return True
                else:
                    self.cap.release()
                    self.cap = None

            logging.warning("OpenCV VideoCapture failed")
            return False

        except ImportError:
            logging.error("OpenCV not available")
            return False
        except Exception as e:
            logging.error(f"Failed to initialize RpiCamera: {e}")
            return False

    def read(self):
        """Read frame from OpenCV VideoCapture"""
        if not self.is_opened or not self.cap:
            return False, None

        try:
            # Import cv2 only when needed
            import cv2

            ret, frame = self.cap.read()
            if ret and frame is not None:
                return True, frame
            else:
                return False, None

        except ImportError:
            logging.error("OpenCV not available")
            return False, None
        except Exception as e:
            logging.error(f"Error reading frame: {e}")
            return False, None

    def release(self):
        """Release camera resources"""
        self.is_opened = False
        if self.cap:
            self.cap.release()
            self.cap = None
        logging.info("RpiCamera released")

def create_camera(width=640, height=480, fps=30, streaming=False):
    """Create RpiCamera instance"""
    return RpiCamera(width, height, fps, streaming)