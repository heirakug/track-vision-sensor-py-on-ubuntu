#!/usr/bin/env python3
"""
フォント表示テスト - MultiModal Tracker GUI設定と同じフォントを表示
"""

import cv2
import numpy as np

def test_font_display():
    """現在のGUI設定と同じフォントを表示してテスト"""

    # テスト画像を作成（800x600の黒背景）
    test_frame = np.zeros((600, 800, 3), dtype=np.uint8)

    # MultiModal Trackerと同じフォント設定
    main_font = cv2.FONT_HERSHEY_DUPLEX
    alt_font = cv2.FONT_HERSHEY_SIMPLEX

    # GUI設定と同じサイズ計算
    width = test_frame.shape[1]
    font_scale = min(0.5, width / 1280 * 0.5)  # GUI と同じ計算

    # 色設定（HUDカラーパレット）
    hud_primary = (0, 255, 255)     # シアン
    hud_secondary = (0, 200, 255)   # ライトブルー
    hud_success = (0, 255, 100)     # グリーン
    hud_warning = (255, 200, 0)     # イエロー
    white = (255, 255, 255)         # 白

    y_start = 50
    y_step = 40

    # タイトル
    cv2.putText(test_frame, "=== FONT TEST - MultiModal Tracker Settings ===",
                (50, y_start), main_font, font_scale * 1.1, hud_primary, 2)

    y_pos = y_start + 60

    # FONT_HERSHEY_DUPLEX テスト（メインフォント）
    cv2.putText(test_frame, "FONT_HERSHEY_DUPLEX (Main GUI Font):",
                (50, y_pos), main_font, font_scale, hud_secondary, 1)

    y_pos += y_step
    # アルファベット大文字
    cv2.putText(test_frame, "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                (70, y_pos), main_font, font_scale, white, 1)

    y_pos += y_step
    # アルファベット小文字
    cv2.putText(test_frame, "abcdefghijklmnopqrstuvwxyz",
                (70, y_pos), main_font, font_scale, white, 1)

    y_pos += y_step
    # 数字と記号
    cv2.putText(test_frame, "0123456789 !@#$%^&*()_+-=[]{}|;':\",./<>?",
                (70, y_pos), main_font, font_scale, white, 1)

    y_pos += y_step
    # GUIで使用される実際のテキスト例
    cv2.putText(test_frame, "H: Hand Tracking  F: Face Tracking  Q: Quit",
                (70, y_pos), main_font, font_scale, hud_success, 1)

    y_pos += y_step
    cv2.putText(test_frame, "Hand 0: (0.723, 0.456)  FPS: 10.5",
                (70, y_pos), main_font, font_scale, hud_success, 1)

    y_pos += y_step + 30

    # FONT_HERSHEY_SIMPLEX テスト（比較用）
    cv2.putText(test_frame, "FONT_HERSHEY_SIMPLEX (Alternative Font):",
                (50, y_pos), alt_font, font_scale, hud_secondary, 1)

    y_pos += y_step
    cv2.putText(test_frame, "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                (70, y_pos), alt_font, font_scale, white, 1)

    y_pos += y_step
    cv2.putText(test_frame, "abcdefghijklmnopqrstuvwxyz",
                (70, y_pos), alt_font, font_scale, white, 1)

    y_pos += y_step
    cv2.putText(test_frame, "0123456789 !@#$%^&*()_+-=[]{}|;':\",./<>?",
                (70, y_pos), alt_font, font_scale, white, 1)

    y_pos += y_step
    cv2.putText(test_frame, "H: Hand Tracking  F: Face Tracking  Q: Quit",
                (70, y_pos), alt_font, font_scale, hud_success, 1)

    y_pos += y_step + 30

    # 異なるthickness設定のテスト
    cv2.putText(test_frame, "Thickness Test (DUPLEX):",
                (50, y_pos), main_font, font_scale, hud_warning, 1)

    y_pos += y_step
    cv2.putText(test_frame, "Thickness=1: ABC123 (Normal text)",
                (70, y_pos), main_font, font_scale, white, 1)

    y_pos += y_step
    cv2.putText(test_frame, "Thickness=2: ABC123 (Headers, FPS)",
                (70, y_pos), main_font, font_scale, white, 2)

    y_pos += y_step
    cv2.putText(test_frame, "Thickness=3: ABC123 (Extra bold)",
                (70, y_pos), main_font, font_scale, white, 3)

    # ウィンドウ表示
    cv2.namedWindow('Font Test - MultiModal Tracker Settings', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Font Test - MultiModal Tracker Settings', 800, 600)

    print("フォントテスト画面を表示中...")
    print("現在のGUI設定:")
    print(f"- メインフォント: FONT_HERSHEY_DUPLEX")
    print(f"- フォントスケール: {font_scale:.3f}")
    print(f"- 基本thickness: 1")
    print(f"- ヘッダーthickness: 2")
    print("")
    print("キー操作:")
    print("- スペースキー: スクリーンショット保存")
    print("- Qキー: 終了")

    while True:
        cv2.imshow('Font Test - MultiModal Tracker Settings', test_frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q') or key == 27:  # Q または ESC
            break
        elif key == ord(' '):  # スペースキー
            filename = 'font_test_screenshot.png'
            cv2.imwrite(filename, test_frame)
            print(f"スクリーンショットを保存: {filename}")

    cv2.destroyAllWindows()
    print("フォントテスト終了")

if __name__ == "__main__":
    test_font_display()