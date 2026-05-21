import cv2
import numpy as np
from deepface import DeepFace
from scipy.spatial import distance

class FaceEngine:
    def __init__(self, db, auth_threshold=0.50, reg_threshold=0.50):
        self.db = db
        self.auth_threshold = auth_threshold  # 入退室用の閾値
        self.reg_threshold = reg_threshold    # 登録の重複チェック用の閾値

    def extract_embedding(self, frame, enforce=True):
        """画像から顔の特徴（ベクトル）を抽出する"""
        try:
            results = DeepFace.represent(frame, model_name="ArcFace", enforce_detection=enforce)
            if results:
                return results[0]["embedding"]
        except Exception:
            pass # 顔が検出されなかった場合は例外を無視
        return None

    def find_match(self, target_embedding, threshold):
        """抽出した特徴をDBと照合し、一致したユーザーのIDと名前と距離を返す"""
        if target_embedding is None:
            return None, None, None

        min_dist = threshold
        matched_id = None
        matched_name = None

        target_vec = np.array(target_embedding, dtype=float).flatten()

        for u_id, info in self.db.get_all_embeddings().items():
            stored = info["embedding"]
            if stored is None:
                continue
            stored_vec = np.array(stored, dtype=float).flatten()
            dist = distance.cosine(target_vec, stored_vec)
            if dist < min_dist:
                min_dist = dist
                matched_id = u_id
                matched_name = info["name"]

        if matched_id is None:
            return None, None, None
        return matched_id, matched_name, min_dist