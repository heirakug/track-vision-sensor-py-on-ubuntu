#!/usr/bin/env python3
"""
手の形状管理・編集ツール
MediaPipeから取得した手の形状を保存・管理するGUIアプリケーション
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import cv2
import mediapipe as mp
import threading
import numpy as np
from gesture_recognizer import GestureRecognizer
import time

class GestureManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Hand Gesture Manager - Track Vision")
        self.root.geometry("1000x800")  # 横幅を広げてログも見やすく
        
        # MediaPipe初期化
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,  # 両手対応
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils
        
        # GestureRecognizer初期化
        self.recognizer = GestureRecognizer()
        
        # OSC送信は無効（main.pyとの競合回避）
        self.osc_enabled = False
        self.osc_client = None
        self.visual_client = None
        
        # カメラ関連
        self.cap = None
        self.camera_running = False
        self.current_landmarks = None  # 主要な手（最初に検出された手）
        self.all_hands_landmarks = []  # 全ての手のランドマーク
        self.recognition_enabled = False
        
        # タイマー関連
        self.capture_timer_active = False
        self.capture_countdown = 0
        self.capture_landmarks_snapshot = None
        
        self.setup_ui()
        self.refresh_gesture_list()
        
    def setup_ui(self):
        """UI構築"""
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # カメラコントロール
        camera_frame = ttk.LabelFrame(main_frame, text="カメラ・認識", padding="10")
        camera_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.camera_button = ttk.Button(camera_frame, text="カメラ開始", command=self.toggle_camera)
        self.camera_button.grid(row=0, column=0, padx=(0, 10))
        
        self.recognition_button = ttk.Button(camera_frame, text="認識開始", command=self.toggle_recognition, state="disabled")
        self.recognition_button.grid(row=0, column=1, padx=(0, 10))
        
        self.capture_button = ttk.Button(camera_frame, text="5秒後に手の形を保存", command=self.start_capture_timer, state="disabled")
        self.capture_button.grid(row=0, column=2)
        
        # カメラプレビュー（TkinterのCanvas）
        self.camera_canvas = tk.Canvas(camera_frame, width=400, height=300, bg="black")
        self.camera_canvas.grid(row=1, column=0, columnspan=3, pady=(10, 5))
        
        # ステータス表示
        self.status_label = ttk.Label(camera_frame, text="カメラ停止中")
        self.status_label.grid(row=2, column=0, columnspan=3, pady=(5, 0))
        
        # ジェスチャー一覧
        list_frame = ttk.LabelFrame(main_frame, text="登録済みジェスチャー", padding="10")
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        # ツリービュー
        columns = ("name", "description", "trigger_data", "created_at")
        self.gesture_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)
        
        self.gesture_tree.heading("name", text="名前")
        self.gesture_tree.heading("description", text="説明")
        self.gesture_tree.heading("trigger_data", text="トリガーデータ")
        self.gesture_tree.heading("created_at", text="作成日時")
        
        self.gesture_tree.column("name", width=150)
        self.gesture_tree.column("description", width=200)
        self.gesture_tree.column("trigger_data", width=150)
        self.gesture_tree.column("created_at", width=150)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.gesture_tree.yview)
        self.gesture_tree.configure(yscrollcommand=scrollbar.set)
        
        self.gesture_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # ボタンフレーム
        button_frame = ttk.Frame(list_frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(button_frame, text="削除", command=self.delete_gesture).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(button_frame, text="更新", command=self.refresh_gesture_list).grid(row=0, column=1, padx=(0, 10))
        ttk.Button(button_frame, text="テスト", command=self.test_gesture).grid(row=0, column=2)
        
        # 設定フレーム
        settings_frame = ttk.LabelFrame(main_frame, text="設定", padding="10")
        settings_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N), padx=(0, 0))
        
        # 類似度閾値
        ttk.Label(settings_frame, text="類似度閾値:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.threshold_var = tk.DoubleVar(value=self.recognizer.settings["similarity_threshold"])
        threshold_scale = ttk.Scale(settings_frame, from_=0.5, to=1.0, variable=self.threshold_var, orient=tk.HORIZONTAL)
        threshold_scale.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.threshold_label = ttk.Label(settings_frame, text=f"{self.threshold_var.get():.2f}")
        self.threshold_label.grid(row=2, column=0, pady=(0, 10))
        
        # クールダウン時間
        ttk.Label(settings_frame, text="クールダウン時間(秒):").grid(row=3, column=0, sticky=tk.W, pady=(0, 5))
        self.cooldown_var = tk.DoubleVar(value=self.recognizer.settings["cooldown_time"])
        cooldown_scale = ttk.Scale(settings_frame, from_=0.1, to=2.0, variable=self.cooldown_var, orient=tk.HORIZONTAL)
        cooldown_scale.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.cooldown_label = ttk.Label(settings_frame, text=f"{self.cooldown_var.get():.1f}")
        self.cooldown_label.grid(row=5, column=0, pady=(0, 10))
        
        # 設定更新
        ttk.Button(settings_frame, text="設定を保存", command=self.save_settings).grid(row=6, column=0, pady=(10, 0))
        
        # 統計情報
        stats_frame = ttk.LabelFrame(settings_frame, text="統計", padding="10")
        stats_frame.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=(20, 0))
        
        self.stats_label = ttk.Label(stats_frame, text="", justify=tk.LEFT)
        self.stats_label.grid(row=0, column=0)
        
        # ログコンソール追加
        log_frame = ttk.LabelFrame(main_frame, text="ログコンソール", padding="10")
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        
        # テキストウィジェットとスクロールバー
        self.log_text = tk.Text(log_frame, height=8, width=80, state=tk.DISABLED, 
                               bg="black", fg="white", font=("Monaco", 9))
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # ログクリアボタン
        clear_log_btn = ttk.Button(log_frame, text="ログクリア", command=self.clear_log)
        clear_log_btn.grid(row=1, column=0, pady=(5, 0), sticky=tk.W)
        
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # バインディング（新しいtkinter用）
        try:
            self.threshold_var.trace_add('write', self.update_threshold_label)
            self.cooldown_var.trace_add('write', self.update_cooldown_label)
        except AttributeError:
            # 古いtkinter用フォールバック
            self.threshold_var.trace('w', self.update_threshold_label)
            self.cooldown_var.trace('w', self.update_cooldown_label)
        
        # グリッドの重み設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=2)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=2)  # ジェスチャー一覧部分
        main_frame.rowconfigure(2, weight=1)  # ログコンソール部分
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        settings_frame.columnconfigure(0, weight=1)
        
        self.update_stats()
        
        # 初期ログメッセージ
        self.log("🚀 Hand Gesture Manager が起動しました")
        self.log(f"📊 登録ジェスチャー数: {len(self.recognizer.gestures)}")
        self.log("🛠️ 管理モード: OSC送信無効（main.pyと競合回避）")
        
    def log(self, message):
        """ログコンソールにメッセージを追加"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}\n"
        
        # テキストウィジェットを一時的に編集可能にする
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, log_line)
        self.log_text.see(tk.END)  # 最新行までスクロール
        self.log_text.config(state=tk.DISABLED)
        
        # コンソールにも出力
        print(f"GUI Log: {message}")
        
    def clear_log(self):
        """ログをクリア"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log("📝 ログをクリアしました")
        
    def send_osc_data(self, address, data):
        """OSCデータ送信（main.pyと同様）"""
        if not self.osc_enabled:
            return
        
        try:
            if self.osc_client:
                self.osc_client.send_message(address, data)
        except (OSError, ConnectionError):
            pass  # OSC Router接続エラーは無視
        
        try:
            if self.visual_client:
                self.visual_client.send_message(address, data)
        except (OSError, ConnectionError):
            pass  # Visual App接続エラーは無視
        
    def update_threshold_label(self, *args):
        self.threshold_label.config(text=f"{self.threshold_var.get():.2f}")
        
    def update_cooldown_label(self, *args):
        self.cooldown_label.config(text=f"{self.cooldown_var.get():.1f}")
        
    def toggle_camera(self):
        """カメラの開始/停止"""
        if not self.camera_running:
            self.start_camera()
        else:
            self.stop_camera()
            
    def start_camera(self):
        """カメラ開始"""
        self.log("📷 カメラを開始しています...")
        self.cap = cv2.VideoCapture(0)
        
        # カメラの設定
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        if not self.cap.isOpened():
            self.log("❌ カメラアクセスに失敗しました")
            messagebox.showerror("エラー", "カメラを開けませんでした")
            return
            
        self.log("✅ カメラが正常に開かれました")
        self.camera_running = True
        self.camera_button.config(text="カメラ停止")
        self.recognition_button.config(state="normal")
        self.status_label.config(text="カメラ動作中")
        
        # カメラスレッド開始
        self.camera_thread = threading.Thread(target=self.camera_loop, daemon=True)
        self.camera_thread.start()
        self.log("📺 OpenCVウィンドウを別画面で開きます...")
        
    def stop_camera(self):
        """カメラ停止"""
        self.camera_running = False
        self.recognition_enabled = False
        
        if self.cap:
            self.cap.release()
            
        cv2.destroyAllWindows()
        
        self.camera_button.config(text="カメラ開始")
        self.recognition_button.config(text="認識開始", state="disabled")
        self.capture_button.config(state="disabled")
        self.status_label.config(text="カメラ停止中")
        
    def toggle_recognition(self):
        """認識の開始/停止"""
        self.recognition_enabled = not self.recognition_enabled
        
        if self.recognition_enabled:
            self.recognition_button.config(text="認識停止")
            self.capture_button.config(state="normal")
            self.status_label.config(text="認識動作中")
        else:
            self.recognition_button.config(text="認識開始")
            self.capture_button.config(state="disabled")
            self.status_label.config(text="カメラ動作中")
            
    def camera_loop(self):
        """カメラメインループ（OpenCVウィンドウなし、Tkinter内プレビュー）"""
        self.log("🎬 カメラループを開始します...")
        self.log("📺 TkinterCanvas内でプレビュー表示します")
        
        from PIL import Image, ImageTk
        
        while self.camera_running:
            ret, frame = self.cap.read()
            if not ret:
                self.log("❌ カメラフレーム読み込み失敗")
                break
                
            frame = cv2.flip(frame, 1)  # 水平反転
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # MediaPipe処理（認識機能が有効でなくても手検出は実行）
            results = self.hands.process(rgb_frame)
            
            # 全ての手のデータをリセット
            self.all_hands_landmarks = []
            self.current_landmarks = None
            
            if results.multi_hand_landmarks:
                for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    # ランドマーク描画（BGRフレームに）
                    self.mp_drawing.draw_landmarks(
                        frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                    
                    # ランドマーク保存（常に実行）
                    landmarks = []
                    for landmark in hand_landmarks.landmark:
                        landmarks.extend([landmark.x, landmark.y])
                    
                    # ランドマーク数を確認
                    if len(landmarks) == 42:
                        # 全ての手のデータを保存
                        self.all_hands_landmarks.append({
                            'id': hand_idx,
                            'landmarks': landmarks
                        })
                        
                        # 最初の手を主要な手として設定
                        if hand_idx == 0:
                            self.current_landmarks = landmarks
                        
                        # 管理モードでは表示のみ、OSC送信なし
                        
                    else:
                        self.log(f"⚠️ 手{hand_idx}: 不正なランドマーク数: {len(landmarks)} (期待値: 42)")
                    
                    # 手のIDを画面に表示
                    palm_center = hand_landmarks.landmark[9]  # 手のひら中心
                    x_pixel = int(palm_center.x * frame.shape[1])
                    y_pixel = int(palm_center.y * frame.shape[0])
                    cv2.putText(frame, f"Hand {hand_idx}", (x_pixel-30, y_pixel-20), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
                
                # 認識処理（認識モード時のみ、最初の手で実行）
                if self.recognition_enabled and self.current_landmarks:
                    match = self.recognizer.recognize_gesture(self.current_landmarks)
                    if match:
                        cv2.putText(frame, f"Recognition: {match['name']} ({match['similarity']:.2f})", 
                                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        if not hasattr(self, 'last_recognized') or self.last_recognized != match['name']:
                            self.log(f"✅ ジェスチャー認識: {match['name']} ({match['similarity']:.3f})")
                            self.last_recognized = match['name']
            else:
                # 手が検出されない場合
                if hasattr(self, 'last_recognized'):
                    delattr(self, 'last_recognized')
            
            # 手検出状態を表示
            hands_count = len(self.all_hands_landmarks)
            if hands_count == 0:
                status_text = "No hands detected"
            elif hands_count == 1:
                status_text = "1 hand detected"
            else:
                status_text = f"{hands_count} hands detected"
            
            cv2.putText(frame, status_text, (10, frame.shape[0] - 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # カウントダウンタイマー表示
            if self.capture_timer_active and self.capture_countdown > 0:
                countdown_text = f"CAPTURE IN {self.capture_countdown}"
                text_size = cv2.getTextSize(countdown_text, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)[0]
                text_x = (frame.shape[1] - text_size[0]) // 2
                text_y = (frame.shape[0] + text_size[1]) // 2
                
                # 背景の半透明オーバーレイ
                overlay = frame.copy()
                cv2.rectangle(overlay, (text_x-20, text_y-40), (text_x+text_size[0]+20, text_y+20), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
                
                # カウントダウンテキスト
                cv2.putText(frame, countdown_text, (text_x, text_y), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 255), 3)
            
            # TkinterCanvas用にフレーム変換
            try:
                # フレームをリサイズ
                display_frame = cv2.resize(frame, (400, 300))
                rgb_display = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                
                # PIL経由でTkinter表示用に変換
                pil_image = Image.fromarray(rgb_display)
                photo = ImageTk.PhotoImage(image=pil_image)
                
                # Canvas更新（メインスレッドで実行）
                self.root.after(0, self.update_camera_display, photo)
                
            except Exception as e:
                self.log(f"⚠️ プレビュー更新エラー: {e}")
                
            time.sleep(0.033)  # 約30FPS
                
        self.stop_camera()
        
    def update_camera_display(self, photo):
        """カメラ表示を更新（メインスレッドで実行）"""
        try:
            self.camera_canvas.delete("all")
            self.camera_canvas.create_image(200, 150, image=photo)  # 400x300の中央
            self.camera_canvas.image = photo  # 参照保持
        except Exception as e:
            # GUI更新エラーは無視（GUIが閉じられた場合など）
            pass
    
    def start_capture_timer(self):
        """5秒カウントダウンタイマーを開始"""
        if not self.current_landmarks:
            messagebox.showwarning("警告", "手が検出されていません")
            self.log("❌ タイマー開始失敗: 手が検出されていません")
            return
        
        if self.capture_timer_active:
            self.log("⚠️ タイマーは既に動作中です")
            return
        
        # カウントダウン開始
        self.capture_timer_active = True
        self.capture_countdown = 5
        self.capture_button.config(text=f"キャンセル（{self.capture_countdown}秒）", command=self.cancel_capture_timer)
        self.log("⏰ 5秒カウントダウン開始！両手でポーズを取ってください")
        
        # タイマー開始
        self.update_capture_timer()
    
    def cancel_capture_timer(self):
        """カウントダウンタイマーをキャンセル"""
        self.capture_timer_active = False
        self.capture_countdown = 0
        self.capture_landmarks_snapshot = None
        self.capture_button.config(text="5秒後に手の形を保存", command=self.start_capture_timer)
        self.log("❌ キャプチャータイマーをキャンセルしました")
    
    def update_capture_timer(self):
        """タイマーを1秒ずつ更新"""
        if not self.capture_timer_active:
            return
        
        if self.capture_countdown > 0:
            self.log(f"⏰ カウントダウン: {self.capture_countdown}秒")
            self.capture_button.config(text=f"キャンセル（{self.capture_countdown}秒）")
            self.capture_countdown -= 1
            
            # 1秒後に再度呼び出し
            self.root.after(1000, self.update_capture_timer)
        else:
            # カウントダウン終了
            self.capture_timer_active = False
            self.capture_button.config(text="5秒後に手の形を保存", command=self.start_capture_timer)
            
            # 現在のランドマークをスナップショット
            if self.current_landmarks:
                self.capture_landmarks_snapshot = self.current_landmarks.copy()
                self.log("📸 ジェスチャーをキャプチャしました！")
                
                # ダイアログを開く（メインスレッドで実行）
                self.root.after(100, self.show_capture_dialog)
            else:
                self.log("❌ キャプチャー失敗: 手が検出されていません")
    
    def show_capture_dialog(self):
        """キャプチャー後のダイアログを表示"""
        if not self.capture_landmarks_snapshot:
            return
        
        self.log("💬 保存ダイアログを開きます")
        
        # ダイアログで名前と説明を入力
        name = simpledialog.askstring("ジェスチャー保存", "ジェスチャー名を入力してください:")
        if not name:
            self.log("⏹️ ジェスチャー保存をキャンセルしました")
            self.capture_landmarks_snapshot = None
            return
            
        description = simpledialog.askstring("ジェスチャー保存", "説明を入力してください（省略可能）:") or ""
        trigger_data = simpledialog.askstring("ジェスチャー保存", f"トリガーデータ（デフォルト: /gesture/{name}）:") or f"/gesture/{name}"
        
        # 保存処理
        try:
            self.recognizer.add_gesture(name, self.capture_landmarks_snapshot, description, "send_message", trigger_data)
            messagebox.showinfo("成功", f"ジェスチャー '{name}' を保存しました")
            self.log(f"✅ ジェスチャー保存成功: '{name}' ({len(self.capture_landmarks_snapshot)}点)")
            self.refresh_gesture_list()
            self.update_stats()
        except Exception as e:
            error_msg = f"保存に失敗しました: {e}"
            messagebox.showerror("エラー", error_msg)
            self.log(f"❌ ジェスチャー保存失敗: {error_msg}")
        
        # スナップショットをクリア
        self.capture_landmarks_snapshot = None
        
    def capture_from_camera(self):
        """カメラから手の形状をキャプチャ"""
        if not self.current_landmarks:
            print("手が検出されていません")
            return
            
        # Tkinterダイアログの代わりにコンソール入力を使用
        print("\n=== ジェスチャーキャプチャ ===")
        print("TkinterのGUIでジェスチャー情報を入力してください")
        
    def capture_gesture(self):
        """現在の手の形を保存"""
        # ランドマークを即座にコピー（カメラループによる変更を防ぐ）
        landmarks_snapshot = self.current_landmarks.copy() if self.current_landmarks else None
        
        # ランドマークの詳細検証
        if not landmarks_snapshot:
            messagebox.showwarning("警告", "手が検出されていません")
            self.log("❌ ジェスチャー保存: 手が検出されていません")
            return
            
        if not isinstance(landmarks_snapshot, list) or len(landmarks_snapshot) != 42:
            messagebox.showwarning("警告", f"ランドマークデータが不正です（期待値: 42点, 実際: {len(landmarks_snapshot) if landmarks_snapshot else 0}点）")
            self.log(f"❌ ジェスチャー保存: 不正なランドマーク数 {len(landmarks_snapshot) if landmarks_snapshot else 'None'}")
            return
            
        self.log(f"📷 ジェスチャー保存準備OK: {len(landmarks_snapshot)}点のランドマークを確認")
        self.log(f"🔍 ランドマーク情報: type={type(landmarks_snapshot)}, first_few_values={landmarks_snapshot[:6]}")
            
        # ダイアログで名前と説明を入力
        name = simpledialog.askstring("ジェスチャー保存", "ジェスチャー名を入力してください:")
        if not name:
            self.log("⏹️ ジェスチャー保存をキャンセルしました")
            return
            
        description = simpledialog.askstring("ジェスチャー保存", "説明を入力してください（省略可能）:") or ""
        trigger_data = simpledialog.askstring("ジェスチャー保存", f"トリガーデータ（デフォルト: /gesture/{name}）:") or f"/gesture/{name}"
        
        # 保存直前に再度検証
        if not landmarks_snapshot or len(landmarks_snapshot) != 42:
            error_msg = f"保存直前にランドマークが無効になりました: type={type(landmarks_snapshot)}, length={len(landmarks_snapshot) if landmarks_snapshot else 'None'}"
            messagebox.showerror("エラー", error_msg)
            self.log(f"❌ {error_msg}")
            return
        
        try:
            self.recognizer.add_gesture(name, landmarks_snapshot, description, "send_message", trigger_data)
            messagebox.showinfo("成功", f"ジェスチャー '{name}' を保存しました")
            self.log(f"✅ ジェスチャー保存成功: '{name}' ({len(landmarks_snapshot)}点)")
            self.refresh_gesture_list()
            self.update_stats()
        except Exception as e:
            error_msg = f"保存に失敗しました: {e}"
            messagebox.showerror("エラー", error_msg)
            self.log(f"❌ ジェスチャー保存失敗: {error_msg}")
            self.log(f"🔍 デバッグ情報: landmarks_snapshot type={type(landmarks_snapshot)}, length={len(landmarks_snapshot) if landmarks_snapshot else 'None'}")
            
            # より詳細なデバッグ情報
            import traceback
            self.log(f"🔧 スタックトレース: {traceback.format_exc()}")
            
    def delete_gesture(self):
        """選択されたジェスチャーを削除"""
        selection = self.gesture_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "削除するジェスチャーを選択してください")
            return
            
        item = self.gesture_tree.item(selection[0])
        gesture_name = item['values'][0]
        
        if messagebox.askyesno("確認", f"ジェスチャー '{gesture_name}' を削除しますか？"):
            if self.recognizer.remove_gesture(gesture_name):
                messagebox.showinfo("成功", f"ジェスチャー '{gesture_name}' を削除しました")
                self.refresh_gesture_list()
                self.update_stats()
            else:
                messagebox.showerror("エラー", "削除に失敗しました")
                
    def test_gesture(self):
        """選択されたジェスチャーとのマッチングテスト"""
        selection = self.gesture_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "テストするジェスチャーを選択してください")
            return
            
        if not self.current_landmarks:
            messagebox.showwarning("警告", "手が検出されていません")
            return
            
        item = self.gesture_tree.item(selection[0])
        gesture_name = item['values'][0]
        
        if gesture_name not in self.recognizer.gestures:
            messagebox.showerror("エラー", "ジェスチャーが見つかりません")
            return
            
        stored_landmarks = self.recognizer.gestures[gesture_name]["landmarks"]
        similarity = self.recognizer.calculate_similarity(self.current_landmarks, stored_landmarks)
        
        threshold = self.recognizer.settings["similarity_threshold"]
        match_result = "マッチ" if similarity >= threshold else "非マッチ"
        
        messagebox.showinfo("テスト結果", 
                          f"ジェスチャー: {gesture_name}\n"
                          f"類似度: {similarity:.3f}\n"
                          f"閾値: {threshold:.3f}\n"
                          f"結果: {match_result}")
                          
    def save_settings(self):
        """設定を保存"""
        self.recognizer.update_settings(
            similarity_threshold=self.threshold_var.get(),
            cooldown_time=self.cooldown_var.get()
        )
        messagebox.showinfo("成功", "設定を保存しました")
        
    def refresh_gesture_list(self):
        """ジェスチャー一覧を更新"""
        for item in self.gesture_tree.get_children():
            self.gesture_tree.delete(item)
            
        gestures = self.recognizer.list_gestures()
        for gesture in gestures:
            self.gesture_tree.insert("", tk.END, values=(
                gesture["name"],
                gesture["description"],
                gesture["trigger_data"],
                gesture["created_at"]
            ))
            
    def update_stats(self):
        """統計情報を更新"""
        stats = self.recognizer.get_stats()
        stats_text = f"登録数: {stats['total_gestures']}\n"
        stats_text += f"認識: {'有効' if stats['recognition_enabled'] else '無効'}\n"
        stats_text += f"閾値: {stats['similarity_threshold']:.2f}\n"
        stats_text += f"クールダウン: {stats['cooldown_time']:.1f}s"
        self.stats_label.config(text=stats_text)
        
    def run(self):
        """アプリケーション実行"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_camera()

if __name__ == "__main__":
    app = GestureManager()
    app.run()