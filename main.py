import mediapipe as mp
import cv2
import numpy as np
from pythonosc.udp_client import SimpleUDPClient
import time
import argparse
import os
import traceback
import logging
import threading
import queue
import signal
from dotenv import load_dotenv
from gesture_recognizer import GestureRecognizer
from rpicamera import create_camera
from rpicam_video import create_video_camera
from PIL import Image, ImageDraw, ImageFont

# .envファイルを読み込み
load_dotenv()

# MediaPipe TensorFlowのログレベルを設定（警告を抑制）
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['GLOG_minloglevel'] = '2'

class ThreadedFrameReader:
    """別スレッドでフレーム読み込みを行うクラス"""

    def __init__(self, camera, buffer_size=2):
        self.camera = camera
        self.frame_queue = queue.Queue(maxsize=buffer_size)
        self.running = False
        self.thread = None
        self.last_frame_time = time.time()
        self.frames_read = 0
        self.consecutive_failures = 0
        self.max_failures = 10

    def start(self):
        """フレーム読み込みスレッドを開始"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._read_frames, daemon=True)
        self.thread.start()
        logging.info("Threaded frame reader started")

    def stop(self):
        """フレーム読み込みスレッドを停止"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        logging.info("Threaded frame reader stopped")

    def _read_frames(self):
        """フレーム読み込みメインループ（別スレッド）"""
        logging.info("Frame reading thread started")

        while self.running:
            try:
                ret, frame = self.camera.read()

                if ret and frame is not None:
                    self.consecutive_failures = 0
                    self.frames_read += 1

                    # 定期的に統計を出力
                    if self.frames_read % 300 == 0:  # 10秒ごと（30fps想定）
                        logging.info(f"Frame reader stats: {self.frames_read} frames read, queue size: {self.frame_queue.qsize()}")

                    # キューが満杯の場合、古いフレームを削除して新しいフレームを追加
                    if self.frame_queue.full():
                        try:
                            self.frame_queue.get_nowait()  # 古いフレームを削除
                        except queue.Empty:
                            pass

                    try:
                        self.frame_queue.put_nowait((ret, frame, time.time()))
                        self.last_frame_time = time.time()
                    except queue.Full:
                        pass  # キューが満杯の場合はフレームをスキップ

                else:
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= self.max_failures:
                        logging.error(f"Too many consecutive frame read failures ({self.consecutive_failures})")
                        break
                    time.sleep(0.01)  # 失敗時は短時間待機

            except Exception as e:
                logging.error(f"Frame reading error: {e}")
                self.consecutive_failures += 1
                if self.consecutive_failures >= self.max_failures:
                    break
                time.sleep(0.01)

        logging.info("Frame reading thread stopped")
        self.running = False

    def get_latest_frame(self, timeout=0.1):
        """最新フレームを取得（タイムアウト付き）"""
        latest_frame = None

        # まず、キューから最新フレームのみを取得（古いフレームは破棄）
        while not self.frame_queue.empty():
            try:
                latest_frame = self.frame_queue.get_nowait()
            except queue.Empty:
                break

        # 最新フレームがない場合は、少し待機してから再度試行
        if latest_frame is None:
            try:
                latest_frame = self.frame_queue.get(timeout=timeout)
            except queue.Empty:
                return False, None

        if latest_frame is not None:
            ret, frame, timestamp = latest_frame
            return ret, frame
        else:
            return False, None

    def is_healthy(self):
        """フレームリーダーが正常に動作しているかチェック"""
        if not self.running:
            return False

        # 最後のフレーム取得から3秒以上経過している場合は異常（より寛容に）
        time_since_last_frame = time.time() - self.last_frame_time
        return time_since_last_frame < 3.0 and self.consecutive_failures < self.max_failures

class MultiModalTracker:
    def __init__(self, enable_hands=True, enable_face=False, enable_pose=False, headless=False):
        # ログ設定
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        # 機能の有効/無効設定
        self.enable_hands = enable_hands
        self.enable_face = enable_face
        self.enable_pose = enable_pose
        self.headless = headless

        # クリーンアップ状態フラグ
        self._cleaned_up = False
        
        # MediaPipe初期化
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        # 手検出 - 極軽量設定（GPU delegate無効化で安定性優先）
        if self.enable_hands:
            self.mp_hands = mp.solutions.hands

            # 超軽量設定（パフォーマンス最優先）
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,  # 1手に限定
                min_detection_confidence=0.5,  # 検出閾値を上げて処理軽減
                min_tracking_confidence=0.3,   # 追跡閾値を上げて処理軽減
                model_complexity=0  # 最軽量モデル
            )
            self.use_gpu_hands = False
            print("✓ Hand tracking enabled (軽量バランス設定)")
            
            # ジェスチャー認識システム初期化
            try:
                self.gesture_recognizer = GestureRecognizer()
                print("✓ Gesture recognition enabled")
            except Exception as e:
                print(f"⚠ Gesture recognition disabled: {e}")
                self.gesture_recognizer = None
        else:
            self.gesture_recognizer = None
        
        # 顔検出
        if self.enable_face:
            self.mp_face_mesh = mp.solutions.face_mesh
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=False,  # 軽量化のため無効化
                min_detection_confidence=0.3,  # 軽量化
                min_tracking_confidence=0.2   # 軽量化
            )
            print("✓ Face tracking enabled")
        
        # ポーズ検出
        if self.enable_pose:
            self.mp_pose = mp.solutions.pose
            self.pose = self.mp_pose.Pose(
                static_image_mode=False,
                model_complexity=0,  # 最軽量モデルに変更
                smooth_landmarks=False,  # 軽量化のため無効化
                enable_segmentation=False,
                smooth_segmentation=False,  # 軽量化のため無効化
                min_detection_confidence=0.3,  # 軽量化
                min_tracking_confidence=0.2   # 軽量化
            )
            print("✓ Pose tracking enabled")
        
        # OSC設定
        osc_router_ip = os.getenv("OSC_ROUTER_IP", "127.0.0.1")
        osc_router_port = int(os.getenv("OSC_ROUTER_PORT", "8000"))
        visual_app_ip = os.getenv("VISUAL_APP_IP", "127.0.0.1")
        visual_app_port = int(os.getenv("VISUAL_APP_PORT", "8003"))
        
        self.osc_client = SimpleUDPClient(osc_router_ip, osc_router_port)
        self.visual_client = SimpleUDPClient(visual_app_ip, visual_app_port)
        
        # OSC設定を保存（表示用）
        self.osc_router_info = f"{osc_router_ip}:{osc_router_port}"
        self.visual_app_info = f"{visual_app_ip}:{visual_app_port}"

        # Pillowフォント設定
        self._init_fonts()
        
        # カメラ設定 - パフォーマンス重視で極小解像度
        self.camera_width = int(os.getenv("CAMERA_WIDTH", "160"))
        self.camera_height = int(os.getenv("CAMERA_HEIGHT", "120"))

        # デバッグ: 環境変数の値を確認
        print(f"DEBUG: CAMERA_WIDTH from env: {os.getenv('CAMERA_WIDTH', 'NOT_SET')}")
        print(f"DEBUG: CAMERA_HEIGHT from env: {os.getenv('CAMERA_HEIGHT', 'NOT_SET')}")
        print(f"DEBUG: Actual camera settings: {self.camera_width}x{self.camera_height}")

        # Raspberry Pi CSIカメラ対応
        self.cap = self._init_camera()

        # スレッド化フレームリーダー初期化（RpiCameraの場合は無効化）
        if self.cap is not None:
            # デバッグ: クラス名を確認
            class_name = str(self.cap.__class__)
            logging.info(f"Camera class detected: {class_name}")

            # RpiCameraやRpiCameraVideoの場合はThreadedFrameReaderを使わない（互換性問題のため）
            if hasattr(self.cap, '__class__') and ('RpiCamera' in class_name or 'RpiCameraVideo' in class_name):
                self.frame_reader = None
                logging.info(f"RpiCamera/RpiCameraVideo detected ({class_name}) - using direct frame reading")
            else:
                self.frame_reader = ThreadedFrameReader(self.cap, buffer_size=2)
                logging.info("ThreadedFrameReader initialized successfully")
        else:
            self.frame_reader = None
            logging.error("Failed to initialize camera")

        # FPS計算用
        self.fps = 0
        self.frame_count = 0
        self.start_time = time.time()

        # パフォーマンス設定
        self.skip_drawing = False  # ハンドトラッキング表示を有効化

        # 表示回転設定
        self.rotation = 0  # 0=通常, 1=90度左, 2=180度, 3=90度右

        # 色調整機能を完全に削除（素のカメラ映像を使用）
        
        print(f"MultiModal Tracker initialized")
        print(f"Camera resolution: {self.camera_width}x{self.camera_height}")
        print(f"Headless mode: {'ON' if self.headless else 'OFF'}")
        print("Sending OSC to:")
        print(f"  - OSC Router: {osc_router_ip}:{osc_router_port}")
        print(f"  - Visual App: {visual_app_ip}:{visual_app_port}")

        # OpenCVウィンドウ設定（ヘッドレスモードでない場合）
        if not self.headless:
            cv2.namedWindow('MultiModal Tracker', cv2.WINDOW_NORMAL)
            # カメラ解像度に応じてウィンドウサイズを調整
            display_width = max(640, self.camera_width * 2)  # 最小640px、カメラの2倍まで
            display_height = max(480, self.camera_height * 2)  # 最小480px、カメラの2倍まで
            cv2.resizeWindow('MultiModal Tracker', display_width, display_height)
            print(f"Display window size: {display_width}x{display_height} (camera: {self.camera_width}x{self.camera_height})")

    def _init_camera(self):
        """カメラの初期化 - RpiCamera優先（安定性重視）"""

        # RpiCameraVideo最優先（rpicam-vid高速ストリーミング）- デフォルト設定
        try:
            logging.info("Trying RpiCameraVideo with default settings...")
            cap = create_video_camera(self.camera_width, self.camera_height, 10)  # AWB設定を削除

            if cap.open():
                logging.info("✓ RpiCameraVideo initialized successfully with default settings")
                self._camera_format = 'BGR'  # RpiCameraVideoはBGRで出力
                return cap
            else:
                logging.warning("RpiCameraVideo failed to open")

        except Exception as e:
            logging.warning(f"RpiCameraVideo error: {e}")

        # RpiCamera Streamingフォールバック
        try:
            logging.info("Trying RpiCamera Streaming with default settings...")
            cap = create_camera(self.camera_width, self.camera_height, 10, streaming=True)  # AWB設定を削除

            if cap.open():
                logging.info("✓ RpiCamera Streaming initialized with default settings")
                self._camera_format = 'BGR'
                return cap
            else:
                logging.warning("RpiCamera Streaming failed to open")

        except Exception as e:
            logging.warning(f"RpiCamera Streaming error: {e}")

        # 通常RpiCameraフォールバック
        try:
            logging.info("Trying standard RpiCamera with default settings...")
            cap = create_camera(self.camera_width, self.camera_height, 10, streaming=False)  # AWB設定を削除

            if cap.open():
                logging.info("✓ Standard RpiCamera initialized with default settings")
                self._camera_format = 'BGR'
                return cap
            else:
                logging.warning("Standard RpiCamera failed to open")

        except Exception as e:
            logging.warning(f"Standard RpiCamera error: {e}")

        # OpenCV VideoCaptureフォールバック（デフォルト設定）
        try:
            logging.info("Trying OpenCV VideoCapture with default settings...")
            cap = cv2.VideoCapture(0)

            if cap.isOpened():
                # 基本設定のみ
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)
                cap.set(cv2.CAP_PROP_FPS, 30)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
                cap.set(cv2.CAP_PROP_CONVERT_RGB, 1)

                # 色調整を一切行わない
                logging.info("OpenCV VideoCapture initialized with no color adjustments")

                self._camera_format = 'BGR'  # デフォルト設定

                # カメラウォームアップ（数フレーム読み捨て）
                for i in range(5):
                    ret, warmup_frame = cap.read()
                    if ret and warmup_frame is not None and warmup_frame.max() > 0:
                        logging.info(f"Warmup frame {i+1}: max={warmup_frame.max()}")
                        break
                    time.sleep(0.1)

                # テストフレーム取得
                ret, test_frame = cap.read()
                if ret and test_frame is not None:
                    actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    actual_fps = cap.get(cv2.CAP_PROP_FPS)

                    # フレーム形状の検証
                    frame_shape = test_frame.shape
                    frame_max = test_frame.max() if test_frame is not None else 0
                    logging.info(f"Test frame shape: {frame_shape}, max_value: {frame_max}")

                    if len(frame_shape) >= 2:
                        frame_h, frame_w = frame_shape[:2]
                        if frame_h > 0 and frame_w > 0 and frame_max > 0:
                            logging.info(f"✓ OpenCV VideoCapture initialized")
                            logging.info(f"Camera resolution: {actual_width}x{actual_height} @ {actual_fps}fps")
                            logging.info(f"Actual frame size: {frame_w}x{frame_h}")
                            return cap
                        else:
                            logging.warning(f"Test frame has no data: dimensions={frame_w}x{frame_h}, max={frame_max}")
                    else:
                        logging.warning(f"Invalid test frame shape: {frame_shape}")

                    cap.release()
                else:
                    logging.warning("OpenCV VideoCapture opened but cannot read frames")
                    cap.release()
            else:
                logging.warning("Failed to open OpenCV VideoCapture")

        except Exception as e:
            logging.warning(f"OpenCV VideoCapture error: {e}")

        # Try OpenCV with V4L2 backend explicitly
        try:
            logging.info("Trying OpenCV VideoCapture with V4L2 backend...")
            cap = cv2.VideoCapture(0, cv2.CAP_V4L2)

            if cap.isOpened():
                # Set properties
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)
                cap.set(cv2.CAP_PROP_FPS, 30)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                # Try different formats
                formats_to_try = [
                    cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'),  # MJPEG format (元の優先設定)
                    cv2.VideoWriter_fourcc('Y', 'U', 'Y', 'V'),  # YUYV format
                ]

                for fmt in formats_to_try:
                    cap.set(cv2.CAP_PROP_FOURCC, fmt)
                    ret, test_frame = cap.read()
                    if ret and test_frame is not None and test_frame.max() > 0:
                        # 色調整を行わない（デフォルトのまま）

                        # フォーマットに応じて処理方法を決定
                        if fmt == cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'):
                            self._camera_format = 'BGR'  # MJPEGは通常BGRとして処理
                            logging.info(f"✓ V4L2 VideoCapture working with MJPEG format + blue reduction")
                        elif fmt == cv2.VideoWriter_fourcc('Y', 'U', 'Y', 'V'):
                            self._camera_format = 'YUYV'
                            logging.info(f"✓ V4L2 VideoCapture working with YUYV format + blue reduction")
                        else:
                            self._camera_format = 'BGR'
                            logging.info(f"✓ V4L2 VideoCapture working with format {fmt} + blue reduction")
                        return cap

                cap.release()

        except Exception as e:
            logging.warning(f"V4L2 VideoCapture error: {e}")

        logging.error("All camera initialization methods failed")
        logging.error("Please check:")
        logging.error("  1. Camera connection")
        logging.error("  2. Lighting conditions")
        logging.error("  3. rpicam-hello --list-cameras")
        return None
        
    def run(self):
        """メインループ - エラーハンドリング強化版"""
        retry_count = 0
        max_retries = 3

        # Signal handler for graceful shutdown
        def signal_handler(signum, frame):
            logging.info(f"Received signal {signum}, shutting down gracefully...")
            self.cleanup()
            exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # フレームリーダーを開始
        if self.frame_reader is not None:
            self.frame_reader.start()
            logging.info("Using threaded frame reading mode")
        else:
            logging.warning("Using fallback direct camera reading mode")
            # フレームリーダーがない場合は従来の方式でフォールバック

        while retry_count < max_retries:
            try:
                logging.info(f"Starting tracker (attempt {retry_count + 1}/{max_retries})")
                self._main_loop()
                break  # 正常終了の場合はループを抜ける

            except KeyboardInterrupt:
                logging.info("User interrupted (Ctrl+C)")
                break

            except Exception as e:
                retry_count += 1
                logging.error(f"Error occurred: {str(e)}")
                logging.error(f"Traceback: {traceback.format_exc()}")

                if retry_count < max_retries:
                    logging.info(f"Restarting in 3 seconds... (attempt {retry_count + 1}/{max_retries})")
                    time.sleep(3)

                    # リソースをクリーンアップして再初期化
                    try:
                        self.cleanup()
                    except:
                        pass

                    # カメラとフレームリーダーを再初期化
                    try:
                        self.cap = self._init_camera()
                        if self.cap is not None:
                            self.frame_reader = ThreadedFrameReader(self.cap, buffer_size=2)
                            self.frame_reader.start()
                        logging.info("Camera and frame reader reinitialized")
                    except Exception as camera_error:
                        logging.error(f"Failed to reinitialize camera: {camera_error}")
                else:
                    logging.error(f"Max retries ({max_retries}) reached. Giving up.")

        self.cleanup()
    
    def _main_loop(self):
        """メインの処理ループ - スレッド化フレーム読み込み対応"""
        consecutive_frame_failures = 0
        max_frame_failures = 10
        no_frame_count = 0
        max_no_frame = 100  # 最大100回連続でフレームなしを許可

        while True:
            # フレーム取得（スレッド版またはフォールバック版）
            if self.frame_reader is not None:
                # スレッドからフレームを取得（タイムアウト付き）
                ret, frame = self.frame_reader.get_latest_frame(timeout=0.1)

                if not ret or frame is None:
                    no_frame_count += 1

                    # フレームリーダーの健全性をチェック
                    if not self.frame_reader.is_healthy():
                        consecutive_frame_failures += 1
                        logging.warning(f"Frame reader unhealthy ({consecutive_frame_failures}/{max_frame_failures})")

                        if consecutive_frame_failures >= max_frame_failures:
                            raise RuntimeError("Frame reader repeatedly failed")

                    # no_frame_countの閾値を大幅に増加（タイムアウト考慮）
                    if no_frame_count >= 300:  # 30秒相当（0.1s * 300）
                        consecutive_frame_failures += 1
                        logging.warning(f"No frames available for too long ({consecutive_frame_failures}/{max_frame_failures})")

                        if consecutive_frame_failures >= max_frame_failures:
                            raise RuntimeError("No frames available for extended period")

                    # フレームが利用できない場合は少し待機（タイムアウトで既に待機済みなので短縮）
                    continue
            else:
                # フォールバック: 直接カメラから読み込み
                ret, frame = self.cap.read()
                if not ret:
                    consecutive_frame_failures += 1
                    logging.warning(f"Failed to read frame ({consecutive_frame_failures}/{max_frame_failures})")

                    if consecutive_frame_failures >= max_frame_failures:
                        raise RuntimeError("Too many consecutive frame read failures")

                    time.sleep(0.1)  # 短時間待機してリトライ
                    continue

            # フレーム処理成功時はカウンターをリセット
            consecutive_frame_failures = 0
            no_frame_count = 0
            
            try:
                # パフォーマンス測定開始
                process_start = time.time()

                # 最小限のフレーム検証のみ
                if frame is None or frame.size == 0:
                    continue

                # フレーム形状の基本チェック
                if len(frame.shape) < 2 or len(frame.shape) > 3:
                    continue

                # フレーム次元の基本検証
                if len(frame.shape) == 3:
                    h, w, c = frame.shape
                    if h <= 0 or w <= 0 or c not in [1, 3]:
                        continue
                elif len(frame.shape) == 2:
                    h, w = frame.shape
                    if h <= 0 or w <= 0:
                        continue

                # フレームを水平反転（鏡像表示）
                frame = cv2.flip(frame, 1)
                flip_time = time.time()

                # シンプルな色変換（元の動作に戻す）
                try:
                    # MediaPipe用にBGR→RGB変換のみ
                    if len(frame.shape) == 3 and frame.shape[2] == 3:
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    else:
                        rgb_frame = frame.copy()

                except Exception as color_error:
                    logging.error(f"Color conversion error: {color_error}")
                    rgb_frame = frame.copy()

                convert_time = time.time()

                # 検出結果を描画
                annotated_frame = frame.copy()

                # 手検出
                hands_start = time.time()
                if self.enable_hands:
                    self.process_hands(rgb_frame, annotated_frame)
                hands_time = time.time()

                # 顔検出
                face_start = time.time()
                if self.enable_face:
                    self.process_face(rgb_frame, annotated_frame)
                face_time = time.time()

                # ポーズ検出
                pose_start = time.time()
                if self.enable_pose:
                    self.process_pose(rgb_frame, annotated_frame)
                pose_time = time.time()

                # パフォーマンス測定終了と表示
                total_process_time = time.time() - process_start
                if self.frame_count % 10 == 0:  # 10フレームごとに出力（デバッグ強化）
                    logging.info(f"Performance stats (ms): "
                               f"Flip: {(flip_time-process_start)*1000:.1f}, "
                               f"Convert: {(convert_time-flip_time)*1000:.1f}, "
                               f"Hands: {(hands_time-hands_start)*1000:.1f}, "
                               f"Face: {(face_time-face_start)*1000:.1f}, "
                               f"Pose: {(pose_time-pose_start)*1000:.1f}, "
                               f"Total: {total_process_time*1000:.1f}")
                
                # FPS計算と表示 (HUDスタイル)
                self.update_fps()
                hud_fps_color = (0, 255, 255) if self.fps >= 25 else ((255, 200, 0) if self.fps >= 15 else (255, 100, 100))

                cv2.putText(annotated_frame, f"FPS: {self.fps:.1f}",
                           (10, annotated_frame.shape[0] - 20), cv2.FONT_HERSHEY_DUPLEX, 0.6, hud_fps_color, 2)

                # Pillowベースのユーザー欄オーバーレイを適用（フレームレートテスト用に一時無効化）
                # annotated_frame = self.apply_gui_overlay(annotated_frame)
                
                # 画面に表示（ヘッドレスモードでない場合のみ）
                if not self.headless:
                    # 表示前のフレーム検証
                    if self.frame_count % 30 == 0:  # 30フレームごとに
                        logging.info(f"Display frame check: shape={annotated_frame.shape}, dtype={annotated_frame.dtype}, min={annotated_frame.min()}, max={annotated_frame.max()}")

                    # 回転適用（色調整はスキップ）
                    rotated_frame = self.apply_rotation(annotated_frame)

                    # 回転に応じたウィンドウサイズでリサイズ（動的サイズ）
                    display_width = max(640, self.camera_width * 2)
                    display_height = max(480, self.camera_height * 2)

                    if self.rotation % 2 == 0:  # 0°または180°
                        display_frame = self.resize_with_aspect_ratio(rotated_frame, display_width, display_height)
                    else:  # 90°または270°
                        display_frame = self.resize_with_aspect_ratio(rotated_frame, display_height, display_width)

                    # 表示フレームの最終検証
                    if display_frame.max() == 0:
                        logging.warning("Display frame is completely black")
                        # テスト用の白フレームを作成
                        display_frame = np.full((480, 800, 3), 128, dtype=np.uint8)

                    cv2.imshow('MultiModal Tracker', display_frame)

                    # キー操作（GUIモードでのみ）
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        logging.info("User requested quit")
                        break
                    elif key == ord('h'):
                        self.toggle_hands()
                    elif key == ord('f'):
                        self.toggle_face()
                    elif key == ord('p'):
                        self.toggle_pose()
                    elif key == ord('g'):
                        self.toggle_gesture_recognition()
                    elif key == ord('r'):
                        self.toggle_rotation()
                    # Cキーの色調整機能を削除
                else:
                    # ヘッドレスモードでは短時間待機のみ
                    time.sleep(0.033)  # ~30 FPS equivalent
                    
            except Exception as frame_error:
                logging.warning(f"Error processing frame: {frame_error}")
                # フレーム処理エラーは致命的ではないので続行
                continue
    
    def process_hands(self, rgb_frame, annotated_frame):
        # 極軽量CPU版のみ使用
        results = self.hands.process(rgb_frame)

        if results.multi_hand_landmarks:
                for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    # 軽量な描画（詳細なスタイリング無し）
                    if not self.skip_drawing:
                        self.mp_drawing.draw_landmarks(
                            annotated_frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)

                    # 手のひらの中心座標を取得（ランドマーク9番）
                    palm_center = hand_landmarks.landmark[9]
                    x, y = palm_center.x, palm_center.y

                    # OSC送信
                    self.send_osc_data("/hand/position", [x, y])
                    self.send_osc_data("/hand/id", [hand_idx])

                    # 全ランドマーク送信
                    landmarks = []
                    for landmark in hand_landmarks.landmark:
                        landmarks.extend([landmark.x, landmark.y])
                    self.send_osc_data("/hand/landmarks", landmarks)

                    # 画面に座標表示 (HUDスタイル)
                    cv2.putText(annotated_frame, f"Hand {hand_idx}: ({x:.3f}, {y:.3f})",
                               (10, 60 + hand_idx * 25), cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 255, 100), 1)

                # ジェスチャー認識（パフォーマンステストのため一時無効化）
                # if hand_idx == 0 and self.gesture_recognizer:
                #     try:
                #         gesture_match = self.gesture_recognizer.recognize_gesture(landmarks)
                #         if gesture_match:
                #             # ジェスチャートリガー送信
                #             self.send_osc_data(gesture_match["trigger_data"], [1.0])
                #             self.send_osc_data("/gesture/recognized", [gesture_match["name"], gesture_match["similarity"]])
                #
                #             # 画面に表示
                #             cv2.putText(annotated_frame, f"Gesture: {gesture_match['name']} ({gesture_match['similarity']:.2f})",
                #                        (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                #
                #             print(f"✓ Gesture recognized: {gesture_match['name']} (similarity: {gesture_match['similarity']:.3f})")
                #     except Exception as e:
                #         logging.warning(f"Gesture recognition error: {e}")
    
    def process_face(self, rgb_frame, annotated_frame):
        results = self.face_mesh.process(rgb_frame)

        if results.multi_face_landmarks:
            for face_idx, face_landmarks in enumerate(results.multi_face_landmarks):
                # 軽量な描画（輪郭のみ）
                if not self.skip_drawing:
                    self.mp_drawing.draw_landmarks(
                        annotated_frame, face_landmarks, self.mp_face_mesh.FACEMESH_CONTOURS)
                
                # 主要ランドマーク（鼻先、目、口など）
                nose_tip = face_landmarks.landmark[1]  # 鼻先
                left_eye = face_landmarks.landmark[33]  # 左目
                right_eye = face_landmarks.landmark[263]  # 右目
                mouth_center = face_landmarks.landmark[13]  # 口中央
                
                # OSC送信
                self.send_osc_data("/face/nose", [nose_tip.x, nose_tip.y])
                self.send_osc_data("/face/left_eye", [left_eye.x, left_eye.y])
                self.send_osc_data("/face/right_eye", [right_eye.x, right_eye.y])
                self.send_osc_data("/face/mouth", [mouth_center.x, mouth_center.y])
                self.send_osc_data("/face/id", [face_idx])
                
                # 画面に表示 (HUDスタイル)
                cv2.putText(annotated_frame, f"Face {face_idx}: Detected",
                           (10, 110 + face_idx * 25), cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 200, 255), 1)
    
    def process_pose(self, rgb_frame, annotated_frame):
        results = self.pose.process(rgb_frame)

        if results.pose_landmarks:
            # 軽量な描画（スタイル無し）
            if not self.skip_drawing:
                self.mp_drawing.draw_landmarks(
                    annotated_frame, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)
            
            # 主要関節の座標
            landmarks = results.pose_landmarks.landmark
            
            # 肩、肘、手首の座標
            left_shoulder = landmarks[11]
            right_shoulder = landmarks[12]
            left_elbow = landmarks[13]
            right_elbow = landmarks[14]
            left_wrist = landmarks[15]
            right_wrist = landmarks[16]
            
            # OSC送信
            self.send_osc_data("/pose/left_shoulder", [left_shoulder.x, left_shoulder.y])
            self.send_osc_data("/pose/right_shoulder", [right_shoulder.x, right_shoulder.y])
            self.send_osc_data("/pose/left_elbow", [left_elbow.x, left_elbow.y])
            self.send_osc_data("/pose/right_elbow", [right_elbow.x, right_elbow.y])
            self.send_osc_data("/pose/left_wrist", [left_wrist.x, left_wrist.y])
            self.send_osc_data("/pose/right_wrist", [right_wrist.x, right_wrist.y])
            
            # 全ポーズランドマーク送信
            pose_data = []
            for landmark in landmarks:
                pose_data.extend([landmark.x, landmark.y, landmark.z])
            self.send_osc_data("/pose/landmarks", pose_data)
            
            # 画面に表示 (HUDスタイル)
            cv2.putText(annotated_frame, "Pose: Detected",
                       (10, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 120, 0), 2)
    
    def send_osc_data(self, address, data):
        """OSCデータ送信 - 接続エラー時は無視"""
        try:
            self.osc_client.send_message(address, data)
        except (OSError, ConnectionError) as e:
            # OSCルーターへの接続エラーは無視（開発時など）
            pass
        
        try:
            self.visual_client.send_message(address, data)
        except (OSError, ConnectionError) as e:
            # Visual Appへの接続エラーは無視（開発時など）
            pass
    
    def update_fps(self):
        """FPS計算"""
        self.frame_count += 1
        if self.frame_count % 30 == 0:
            current_time = time.time()
            self.fps = 30 / (current_time - self.start_time)
            self.start_time = current_time
    
    def toggle_hands(self):
        """手検出のON/OFF切り替え"""
        if hasattr(self, 'hands'):
            self.enable_hands = not self.enable_hands
            print(f"Hand tracking: {'ON' if self.enable_hands else 'OFF'}")
    
    def toggle_face(self):
        """顔検出のON/OFF切り替え"""
        if hasattr(self, 'face_mesh'):
            self.enable_face = not self.enable_face
            print(f"Face tracking: {'ON' if self.enable_face else 'OFF'}")
    
    def toggle_pose(self):
        """ポーズ検出のON/OFF切り替え"""
        if hasattr(self, 'pose'):
            self.enable_pose = not self.enable_pose
            print(f"Pose tracking: {'ON' if self.enable_pose else 'OFF'}")
    
    def toggle_gesture_recognition(self):
        """ジェスチャー認識のON/OFF切り替え"""
        if self.gesture_recognizer:
            current_state = self.gesture_recognizer.settings["recognition_enabled"]
            self.gesture_recognizer.update_settings(recognition_enabled=not current_state)
            new_state = self.gesture_recognizer.settings["recognition_enabled"]
            print(f"Gesture recognition: {'ON' if new_state else 'OFF'}")
        else:
            print("Gesture recognition: Not available")

    def toggle_rotation(self):
        """表示回転の切り替え (0° -> 90°左 -> 180° -> 90°右 -> 0°)"""
        self.rotation = (self.rotation + 1) % 4
        rotation_names = ["通常", "90°左", "180°", "90°右"]
        print(f"Display rotation: {rotation_names[self.rotation]}")

        # ウィンドウサイズを回転に合わせて調整（動的サイズ）
        if not self.headless:
            display_width = max(640, self.camera_width * 2)
            display_height = max(480, self.camera_height * 2)

            if self.rotation % 2 == 0:  # 0°または180°
                cv2.resizeWindow('MultiModal Tracker', display_width, display_height)
            else:  # 90°または270°
                cv2.resizeWindow('MultiModal Tracker', display_height, display_width)

    def apply_rotation(self, frame):
        """フレームに回転を適用"""
        if self.rotation == 0:
            return frame
        elif self.rotation == 1:  # 90度左回転
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif self.rotation == 2:  # 180度回転
            return cv2.rotate(frame, cv2.ROTATE_180)
        elif self.rotation == 3:  # 90度右回転
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        else:
            return frame

    # 色調整関連関数を削除 - 素のカメラ映像を使用
    

    def resize_with_aspect_ratio(self, frame, target_width, target_height):
        """アスペクト比を保持してリサイズ（レターボックス方式）"""
        # 安全チェック
        if frame is None or frame.size == 0:
            logging.warning("Invalid frame for resize, creating black frame")
            return np.zeros((target_height, target_width, 3), dtype=np.uint8)

        h, w = frame.shape[:2]

        # 次元の安全チェック
        if h <= 0 or w <= 0 or h >= 32767 or w >= 32767:
            logging.warning(f"Invalid frame dimensions for resize: {w}x{h}")
            return np.zeros((target_height, target_width, 3), dtype=np.uint8)

        aspect_ratio = w / h
        target_aspect = target_width / target_height

        if aspect_ratio > target_aspect:
            # 幅基準でリサイズ
            new_width = target_width
            new_height = max(1, int(target_width / aspect_ratio))
        else:
            # 高さ基準でリサイズ
            new_height = target_height
            new_width = max(1, int(target_height * aspect_ratio))

        # 新しい次元の安全チェック
        if new_width <= 0 or new_height <= 0 or new_width >= 32767 or new_height >= 32767:
            logging.warning(f"Invalid new dimensions: {new_width}x{new_height}")
            return np.zeros((target_height, target_width, 3), dtype=np.uint8)

        try:
            # リサイズ
            resized = cv2.resize(frame, (new_width, new_height))

            # パディング（黒帯追加）
            result = np.zeros((target_height, target_width, 3), dtype=np.uint8)
            y_offset = (target_height - new_height) // 2
            x_offset = (target_width - new_width) // 2

            # 境界チェック
            if (y_offset >= 0 and x_offset >= 0 and
                y_offset + new_height <= target_height and
                x_offset + new_width <= target_width):
                result[y_offset:y_offset+new_height, x_offset:x_offset+new_width] = resized

            return result

        except Exception as e:
            logging.error(f"Resize error: {e}")
            return np.zeros((target_height, target_width, 3), dtype=np.uint8)

    def cleanup(self):
        """リソースのクリーンアップ（重複実行防止付き）"""
        if hasattr(self, '_cleaned_up') and self._cleaned_up:
            return  # 既にクリーンアップ済み

        self._cleaned_up = True

        try:
            # フレームリーダーを停止
            if hasattr(self, 'frame_reader') and self.frame_reader is not None:
                self.frame_reader.stop()
                self.frame_reader = None
        except Exception as e:
            logging.warning(f"Frame reader cleanup error: {e}")

        try:
            # カメラを解放
            if hasattr(self, 'cap') and self.cap is not None:
                self.cap.release()
                self.cap = None
        except Exception as e:
            logging.warning(f"Camera cleanup error: {e}")

        try:
            # OpenCVウィンドウを閉じる
            if not self.headless:
                cv2.destroyAllWindows()
        except Exception as e:
            logging.warning(f"Window cleanup error: {e}")

        print("MultiModal tracker stopped")

    def _init_fonts(self):
        """Pillowフォントの初期化"""
        try:
            font_path = 'fonts/static/Roboto-Regular.ttf'
            if os.path.exists(font_path):
                self.font_small = ImageFont.truetype(font_path, 14)
                self.font_medium = ImageFont.truetype(font_path, 16)
                self.font_large = ImageFont.truetype(font_path, 20)
                print("✓ Roboto Regular font loaded successfully")
            else:
                raise FileNotFoundError("Roboto font not found")
        except Exception as e:
            print(f"⚠ Using default font: {e}")
            self.font_small = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_large = ImageFont.load_default()

    def create_gui_overlay(self, frame_width, frame_height):
        """GUIオーバーレイをPillowで作成"""
        # 透明な画像を作成
        overlay = Image.new('RGBA', (frame_width, frame_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # カラーパレット
        primary_color = (0, 255, 255, 200)     # シアン
        success_color = (0, 255, 100, 200)     # グリーン
        warning_color = (255, 200, 0, 200)     # イエロー
        inactive_color = (80, 80, 80, 200)     # グレー
        background_color = (0, 0, 0, 140)      # 半透明背景

        # コントロールパネル背景
        panel_width = min(320, frame_width // 2)
        panel_height = min(240, frame_height // 3)
        panel_x = frame_width - panel_width

        draw.rectangle([panel_x, 0, frame_width, panel_height], fill=background_color)

        # タイトル
        title_y = 10
        draw.text((panel_x + 10, title_y), "=== CONTROLS ===",
                 font=self.font_medium, fill=primary_color)

        # コントロール情報
        y_offset = title_y + 30
        line_height = 22

        # ジェスチャー認識の状態を取得
        gesture_enabled = False
        if self.gesture_recognizer:
            gesture_enabled = self.gesture_recognizer.settings["recognition_enabled"]

        rotation_names = ["通常", "90°左", "180°", "90°右"]
        controls = [
            ("H: Hand Tracking", success_color if self.enable_hands else inactive_color),
            ("F: Face Tracking", success_color if self.enable_face else inactive_color),
            ("P: Pose Tracking", success_color if self.enable_pose else inactive_color),
            ("G: Gesture Recognition", warning_color if gesture_enabled else inactive_color),
            (f"R: Rotation ({rotation_names[self.rotation]})", primary_color),
            ("Q: Quit", (220, 220, 220, 200))
        ]

        for control_text, color in controls:
            draw.text((panel_x + 10, y_offset), control_text,
                     font=self.font_small, fill=color)
            y_offset += line_height

        # OSC情報
        y_offset += 20
        draw.text((panel_x + 10, y_offset), "=== OSC OUTPUT ===",
                 font=self.font_medium, fill=primary_color)
        y_offset += 30

        draw.text((panel_x + 10, y_offset), f"Router: {self.osc_router_info}",
                 font=self.font_small, fill=primary_color)
        y_offset += line_height
        draw.text((panel_x + 10, y_offset), f"Visual: {self.visual_app_info}",
                 font=self.font_small, fill=primary_color)

        # アクティブ機能表示（左上）
        status_text = []
        if self.enable_hands: status_text.append("HANDS")
        if self.enable_face: status_text.append("FACE")
        if self.enable_pose: status_text.append("POSE")

        if status_text:
            status_display = " | ".join(status_text)
            draw.text((10, 10), status_display, font=self.font_large, fill=primary_color)
        else:
            draw.text((10, 10), "ALL DISABLED", font=self.font_large, fill=warning_color)

        return overlay

    def apply_gui_overlay(self, cv_frame):
        """OpenCVフレームにPillowオーバーレイを適用"""
        try:
            # OpenCVフレームをPILに変換
            pil_frame = Image.fromarray(cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB))

            # GUIオーバーレイを作成
            overlay = self.create_gui_overlay(pil_frame.width, pil_frame.height)

            # オーバーレイを合成
            combined = Image.alpha_composite(
                pil_frame.convert('RGBA'), overlay
            ).convert('RGB')

            # OpenCVフレームに戻す
            return cv2.cvtColor(np.array(combined), cv2.COLOR_RGB2BGR)

        except Exception as e:
            logging.warning(f"GUI overlay error: {e}")
            return cv_frame

def parse_arguments():
    parser = argparse.ArgumentParser(description='MultiModal Tracker with MediaPipe')
    parser.add_argument('--hands', action='store_true', default=True,
                       help='Enable hand tracking (default: True)')
    parser.add_argument('--no-hands', action='store_true',
                       help='Disable hand tracking')
    parser.add_argument('--face', action='store_true',
                       help='Enable face tracking')
    parser.add_argument('--pose', action='store_true',
                       help='Enable pose tracking')
    parser.add_argument('--all', action='store_true',
                       help='Enable all tracking modes')
    parser.add_argument('--headless', action='store_true',
                       help='Run without GUI display (for headless systems)')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    
    # 引数に基づいて機能を設定
    enable_hands = args.hands and not args.no_hands
    enable_face = args.face or args.all
    enable_pose = args.pose or args.all
    
    if args.all:
        enable_hands = True
    
    # 何も有効でない場合はデフォルトで手のみ
    if not (enable_hands or enable_face or enable_pose):
        enable_hands = True
    
    print("=== MultiModal Tracker ===")
    if not args.headless:
        print("Controls:")
        print("  Q: Quit")
        print("  H: Toggle hand tracking")
        print("  F: Toggle face tracking")
        print("  P: Toggle pose tracking")
        print("  G: Toggle gesture recognition")
        print("  R: Rotate display (0° -> 90°左 -> 180° -> 90°右)")
        print()
    else:
        print("Running in headless mode (no GUI)")
        print("Use Ctrl+C to quit")
        print()
    print("Gesture Manager:")
    print("  Run 'python gesture_manager.py' to manage hand gestures")
    print()
    
    tracker = MultiModalTracker(
        enable_hands=enable_hands,
        enable_face=enable_face,
        enable_pose=enable_pose,
        headless=args.headless
    )
    tracker.run()
