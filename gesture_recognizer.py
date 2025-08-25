import json
import numpy as np
import os
from typing import Dict, List, Tuple, Optional
import time

class GestureRecognizer:
    """手の形状認識・比較システム"""
    
    def __init__(self, gestures_file="gestures.json"):
        self.gestures_file = gestures_file
        self.gestures = {}
        self.settings = {
            "similarity_threshold": 0.85,
            "recognition_enabled": True,
            "cooldown_time": 0.5  # 連続認識を防ぐクールダウン時間（秒）
        }
        self.last_trigger_time = {}
        self.load_gestures()
    
    def load_gestures(self):
        """保存された手の形状データを読み込み"""
        if os.path.exists(self.gestures_file):
            try:
                with open(self.gestures_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.gestures = data.get("hand_gestures", {})
                    self.settings.update(data.get("settings", {}))
                print(f"Loaded {len(self.gestures)} gestures from {self.gestures_file}")
            except Exception as e:
                print(f"Error loading gestures: {e}")
                self.gestures = {}
    
    def save_gestures(self):
        """手の形状データを保存"""
        data = {
            "hand_gestures": self.gestures,
            "settings": self.settings
        }
        try:
            with open(self.gestures_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Saved {len(self.gestures)} gestures to {self.gestures_file}")
        except Exception as e:
            print(f"Error saving gestures: {e}")
    
    def normalize_landmarks(self, landmarks: List[float]) -> np.ndarray:
        """ランドマークを正規化（手のひら中心・スケール調整）"""
        if len(landmarks) != 42:  # 21点 x 2座標
            raise ValueError(f"Expected 42 values (21 landmarks x 2), got {len(landmarks)}")
        
        # 2D座標に変換
        points = np.array(landmarks).reshape(21, 2)
        
        # 手のひら中心（ランドマーク9番）を基準点とする
        palm_center = points[9]
        
        # 中心を原点に移動
        centered_points = points - palm_center
        
        # スケール正規化（手のひら〜中指先端の距離を基準）
        middle_finger_tip = centered_points[12]  # 中指先端
        scale = np.linalg.norm(middle_finger_tip)
        
        if scale > 0:
            normalized_points = centered_points / scale
        else:
            normalized_points = centered_points
        
        return normalized_points.flatten()
    
    def calculate_similarity(self, landmarks1: List[float], landmarks2: List[float]) -> float:
        """2つの手の形状の類似度を計算（コサイン類似度）"""
        try:
            norm1 = self.normalize_landmarks(landmarks1)
            norm2 = self.normalize_landmarks(landmarks2)
            
            # コサイン類似度を計算
            dot_product = np.dot(norm1, norm2)
            norm_product = np.linalg.norm(norm1) * np.linalg.norm(norm2)
            
            if norm_product == 0:
                return 0.0
            
            similarity = dot_product / norm_product
            # -1〜1の範囲を0〜1に変換
            return (similarity + 1) / 2
            
        except Exception as e:
            print(f"Error calculating similarity: {e}")
            return 0.0
    
    def recognize_gesture(self, landmarks: List[float]) -> Optional[Dict]:
        """現在の手の形状を認識して、マッチするジェスチャーを返す"""
        if not self.settings["recognition_enabled"] or not self.gestures:
            return None
        
        best_match = None
        best_similarity = 0.0
        current_time = time.time()
        
        for gesture_name, gesture_data in self.gestures.items():
            similarity = self.calculate_similarity(landmarks, gesture_data["landmarks"])
            
            if similarity > best_similarity and similarity >= self.settings["similarity_threshold"]:
                # クールダウンチェック
                last_trigger = self.last_trigger_time.get(gesture_name, 0)
                if current_time - last_trigger >= self.settings["cooldown_time"]:
                    best_match = {
                        "name": gesture_name,
                        "similarity": similarity,
                        "trigger_action": gesture_data.get("trigger_action"),
                        "trigger_data": gesture_data.get("trigger_data"),
                        "description": gesture_data.get("description", gesture_name)
                    }
                    best_similarity = similarity
        
        if best_match:
            self.last_trigger_time[best_match["name"]] = current_time
        
        return best_match
    
    def add_gesture(self, name: str, landmarks: List[float], description: str = "", 
                   trigger_action: str = "send_message", trigger_data: str = ""):
        """新しい手の形状を登録"""
        if len(landmarks) != 42:
            raise ValueError(f"Expected 42 values (21 landmarks x 2), got {len(landmarks)}")
        
        self.gestures[name] = {
            "landmarks": landmarks,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "description": description,
            "trigger_action": trigger_action,
            "trigger_data": trigger_data or f"/gesture/{name}"
        }
        self.save_gestures()
        print(f"Added gesture: {name}")
    
    def remove_gesture(self, name: str) -> bool:
        """手の形状を削除"""
        if name in self.gestures:
            del self.gestures[name]
            self.save_gestures()
            print(f"Removed gesture: {name}")
            return True
        return False
    
    def list_gestures(self) -> List[Dict]:
        """登録されている手の形状一覧を取得"""
        gesture_list = []
        for name, data in self.gestures.items():
            gesture_list.append({
                "name": name,
                "description": data.get("description", ""),
                "created_at": data.get("created_at", ""),
                "trigger_action": data.get("trigger_action", ""),
                "trigger_data": data.get("trigger_data", "")
            })
        return gesture_list
    
    def update_settings(self, **kwargs):
        """設定を更新"""
        for key, value in kwargs.items():
            if key in self.settings:
                self.settings[key] = value
        self.save_gestures()
        print(f"Updated settings: {kwargs}")
    
    def get_stats(self) -> Dict:
        """統計情報を取得"""
        return {
            "total_gestures": len(self.gestures),
            "recognition_enabled": self.settings["recognition_enabled"],
            "similarity_threshold": self.settings["similarity_threshold"],
            "cooldown_time": self.settings["cooldown_time"]
        }

if __name__ == "__main__":
    # テスト用のサンプルコード
    recognizer = GestureRecognizer()
    
    # サンプルランドマーク（実際にはMediaPipeから取得）
    sample_landmarks = [0.5] * 42  # 21点 x 2座標のダミーデータ
    
    print("Gesture Recognizer Test")
    print(f"Stats: {recognizer.get_stats()}")
    
    # サンプルジェスチャー追加（実際の使用では別のスクリプトから行う）
    # recognizer.add_gesture("test_gesture", sample_landmarks, "テスト用ジェスチャー")