#!/usr/bin/env python3
"""
Pillow GUI Test Only
Test the new GUI overlay functionality without camera dependencies
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
import time

class TestGUI:
    def __init__(self):
        self._init_fonts()
        self.enable_hands = True
        self.enable_face = False
        self.enable_pose = True
        self.rotation = 0
        self.osc_router_info = "127.0.0.1:8000"
        self.visual_app_info = "127.0.0.1:8003"
        self.gesture_recognizer = None
        self.fps = 30.0

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

        # FPS表示（左下）
        fps_color = primary_color if self.fps >= 25 else warning_color
        draw.text((10, frame_height - 30), f"FPS: {self.fps:.1f}",
                 font=self.font_medium, fill=fps_color)

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
            print(f"GUI overlay error: {e}")
            return cv_frame

    def test_gui(self):
        """GUI表示テスト"""
        print("Testing Pillow GUI overlay...")

        # テストフレーム作成（グラデーション背景）
        width, height = 800, 600
        test_frame = np.zeros((height, width, 3), dtype=np.uint8)

        # グラデーション背景作成
        for y in range(height):
            for x in range(width):
                test_frame[y, x] = [
                    int(50 + (x / width) * 100),      # Red gradient
                    int(30 + (y / height) * 80),      # Green gradient
                    int(80 + ((x + y) / (width + height)) * 100)  # Blue gradient
                ]

        cv2.namedWindow('GUI Test', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('GUI Test', width, height)

        print("Controls:")
        print("  H: Toggle Hand Tracking")
        print("  F: Toggle Face Tracking")
        print("  P: Toggle Pose Tracking")
        print("  R: Toggle Rotation")
        print("  Q: Quit")
        print()

        frame_count = 0
        start_time = time.time()

        while True:
            # FPS更新
            frame_count += 1
            if frame_count % 30 == 0:
                current_time = time.time()
                self.fps = 30 / (current_time - start_time)
                start_time = current_time

            # GUIオーバーレイを適用
            display_frame = self.apply_gui_overlay(test_frame)

            cv2.imshow('GUI Test', display_frame)

            # キー操作
            key = cv2.waitKey(30) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('h'):
                self.enable_hands = not self.enable_hands
                print(f"Hand tracking: {'ON' if self.enable_hands else 'OFF'}")
            elif key == ord('f'):
                self.enable_face = not self.enable_face
                print(f"Face tracking: {'ON' if self.enable_face else 'OFF'}")
            elif key == ord('p'):
                self.enable_pose = not self.enable_pose
                print(f"Pose tracking: {'ON' if self.enable_pose else 'OFF'}")
            elif key == ord('r'):
                self.rotation = (self.rotation + 1) % 4
                rotation_names = ["通常", "90°左", "180°", "90°右"]
                print(f"Rotation: {rotation_names[self.rotation]}")

        cv2.destroyAllWindows()
        print("GUI test completed!")

if __name__ == "__main__":
    test_gui = TestGUI()
    test_gui.test_gui()