import mediapipe as mp
import cv2
from pythonosc.udp_client import SimpleUDPClient
import time
import argparse
import os
import traceback
import logging

class MultiModalTracker:
    def __init__(self, enable_hands=True, enable_face=False, enable_pose=False):
        # ログ設定
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        # 機能の有効/無効設定
        self.enable_hands = enable_hands
        self.enable_face = enable_face
        self.enable_pose = enable_pose
        
        # MediaPipe初期化
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        # 手検出
        if self.enable_hands:
            self.mp_hands = mp.solutions.hands
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.5
            )
            print("✓ Hand tracking enabled")
        
        # 顔検出
        if self.enable_face:
            self.mp_face_mesh = mp.solutions.face_mesh
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            print("✓ Face tracking enabled")
        
        # ポーズ検出
        if self.enable_pose:
            self.mp_pose = mp.solutions.pose
            self.pose = self.mp_pose.Pose(
                static_image_mode=False,
                model_complexity=1,
                smooth_landmarks=True,
                enable_segmentation=False,
                smooth_segmentation=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
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
        
        # カメラ設定
        self.camera_width = int(os.getenv("CAMERA_WIDTH", "1280"))
        self.camera_height = int(os.getenv("CAMERA_HEIGHT", "720"))
        
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)
        
        # FPS計算用
        self.fps = 0
        self.frame_count = 0
        self.start_time = time.time()
        
        print(f"MultiModal Tracker initialized")
        print(f"Camera resolution: {self.camera_width}x{self.camera_height}")
        print("Sending OSC to:")
        print(f"  - OSC Router: {osc_router_ip}:{osc_router_port}") 
        print(f"  - Visual App: {visual_app_ip}:{visual_app_port}")
        
    def run(self):
        """メインループ - エラーハンドリング強化版"""
        retry_count = 0
        max_retries = 3
        
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
                    
                    # カメラを再初期化
                    try:
                        self.cap = cv2.VideoCapture(0)
                        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
                        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)
                        logging.info("Camera reinitialized")
                    except Exception as camera_error:
                        logging.error(f"Failed to reinitialize camera: {camera_error}")
                else:
                    logging.error(f"Max retries ({max_retries}) reached. Giving up.")
                    
        self.cleanup()
    
    def _main_loop(self):
        """メインの処理ループ"""
        consecutive_frame_failures = 0
        max_frame_failures = 10
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                consecutive_frame_failures += 1
                logging.warning(f"Failed to read frame ({consecutive_frame_failures}/{max_frame_failures})")
                
                if consecutive_frame_failures >= max_frame_failures:
                    raise RuntimeError("Too many consecutive frame read failures")
                
                time.sleep(0.1)  # 短時間待機してリトライ
                continue
            
            # フレーム読み取り成功時はカウンターをリセット
            consecutive_frame_failures = 0
            
            try:
                # フレームを水平反転（鏡像表示）
                frame = cv2.flip(frame, 1)
                
                # OpenCVのBGRからRGBに変換
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # 検出結果を描画
                annotated_frame = frame.copy()
                
                # 手検出
                if self.enable_hands:
                    self.process_hands(rgb_frame, annotated_frame)
                
                # 顔検出
                if self.enable_face:
                    self.process_face(rgb_frame, annotated_frame)
                
                # ポーズ検出
                if self.enable_pose:
                    self.process_pose(rgb_frame, annotated_frame)
                
                # FPS計算と表示
                self.update_fps()
                cv2.putText(annotated_frame, f"FPS: {self.fps:.1f}", 
                           (10, annotated_frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                # コントロール情報表示
                self.draw_control_info(annotated_frame)
                
                # 画面に表示
                cv2.imshow('MultiModal Tracker', annotated_frame)
                
                # キー操作
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
                    
            except Exception as frame_error:
                logging.warning(f"Error processing frame: {frame_error}")
                # フレーム処理エラーは致命的ではないので続行
                continue
    
    def process_hands(self, rgb_frame, annotated_frame):
        results = self.hands.process(rgb_frame)
        
        if results.multi_hand_landmarks:
            for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                # ランドマークを描画
                self.mp_drawing.draw_landmarks(
                    annotated_frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS,
                    self.mp_drawing_styles.get_default_hand_landmarks_style(),
                    self.mp_drawing_styles.get_default_hand_connections_style())
                
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
                
                # 画面に座標表示
                cv2.putText(annotated_frame, f"Hand {hand_idx}: ({x:.3f}, {y:.3f})", 
                           (10, 60 + hand_idx * 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    
    def process_face(self, rgb_frame, annotated_frame):
        results = self.face_mesh.process(rgb_frame)
        
        if results.multi_face_landmarks:
            for face_idx, face_landmarks in enumerate(results.multi_face_landmarks):
                # フェイスメッシュを描画
                self.mp_drawing.draw_landmarks(
                    annotated_frame, face_landmarks, self.mp_face_mesh.FACEMESH_CONTOURS,
                    None, self.mp_drawing_styles.get_default_face_mesh_contours_style())
                
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
                
                # 画面に表示
                cv2.putText(annotated_frame, f"Face {face_idx}: Detected", 
                           (10, 110 + face_idx * 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    
    def process_pose(self, rgb_frame, annotated_frame):
        results = self.pose.process(rgb_frame)
        
        if results.pose_landmarks:
            # ポーズランドマークを描画
            self.mp_drawing.draw_landmarks(
                annotated_frame, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS,
                self.mp_drawing_styles.get_default_pose_landmarks_style())
            
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
            
            # 画面に表示
            cv2.putText(annotated_frame, "Pose: Detected", 
                       (10, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    
    def send_osc_data(self, address, data):
        """OSCデータ送信"""
        self.osc_client.send_message(address, data)
        self.visual_client.send_message(address, data)
    
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
    
    def draw_control_info(self, frame):
        """コントロール情報と状態を画面に表示"""
        height, width = frame.shape[:2]
        
        # パネルサイズを画面サイズに応じて調整
        panel_width = min(320, width // 2)  # 最大320px、画面幅の半分まで
        panel_height = min(240, height // 3)  # 最大240px、画面高さの1/3まで
        
        # 背景を暗くする領域（右上）
        overlay = frame.copy()
        cv2.rectangle(overlay, (width-panel_width, 0), (width, panel_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # テキスト設定
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = min(0.5, width / 1280 * 0.5)  # 画面サイズに応じてフォントサイズ調整
        thickness = 1
        text_x = width - panel_width + 10  # パネル左端から10px
        
        # キーボードコントロール表示
        y_offset = 20
        cv2.putText(frame, "=== CONTROLS ===", (text_x, y_offset), font, font_scale * 1.2, (255, 255, 255), 2)
        
        y_offset += 25
        controls = [
            ("H: Hand Tracking", (0, 255, 0) if self.enable_hands else (100, 100, 100)),
            ("F: Face Tracking", (0, 255, 0) if self.enable_face else (100, 100, 100)),
            ("P: Pose Tracking", (0, 255, 0) if self.enable_pose else (100, 100, 100)),
            ("Q: Quit", (255, 255, 255))
        ]
        
        for control_text, color in controls:
            cv2.putText(frame, control_text, (text_x, y_offset), font, font_scale, color, thickness)
            y_offset += 20
        
        # OSC送信先情報
        y_offset += 15
        cv2.putText(frame, "=== OSC OUTPUT ===", (text_x, y_offset), font, font_scale * 1.2, (255, 255, 255), 2)
        y_offset += 25
        
        cv2.putText(frame, f"Router: {self.osc_router_info}", (text_x, y_offset), font, font_scale, (0, 255, 255), thickness)
        y_offset += 20
        cv2.putText(frame, f"Visual: {self.visual_app_info}", (text_x, y_offset), font, font_scale, (0, 255, 255), thickness)
        
        # アクティブな機能の状態表示（左上）
        status_text = []
        if self.enable_hands: status_text.append("HANDS")
        if self.enable_face: status_text.append("FACE")
        if self.enable_pose: status_text.append("POSE")
        
        if status_text:
            cv2.putText(frame, " | ".join(status_text), (10, 30), font, 0.7, (0, 255, 255), 2)
        else:
            cv2.putText(frame, "ALL DISABLED", (10, 30), font, 0.7, (0, 0, 255), 2)

    def cleanup(self):
        self.cap.release()
        cv2.destroyAllWindows()
        print("MultiModal tracker stopped")

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
    print("Controls:")
    print("  Q: Quit")
    print("  H: Toggle hand tracking")
    print("  F: Toggle face tracking") 
    print("  P: Toggle pose tracking")
    print()
    
    tracker = MultiModalTracker(
        enable_hands=enable_hands,
        enable_face=enable_face,
        enable_pose=enable_pose
    )
    tracker.run()
