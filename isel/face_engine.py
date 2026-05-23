from __future__ import annotations
import cv2
import numpy as np
from deepface import DeepFace
from scipy.spatial import distance


class FaceEngine:
    def __init__(self, get_embeddings, auth_threshold: float = 0.55, reg_threshold: float = 0.50) -> None:
        self.get_embeddings = get_embeddings
        self.auth_threshold = auth_threshold
        self.reg_threshold = reg_threshold

    def extract_embedding(self, frame, enforce: bool = True):
        """Extract ArcFace embedding from an OpenCV frame. Returns None if no face found."""
        try:
            results = DeepFace.represent(frame, model_name='ArcFace', enforce_detection=enforce)
            if results:
                return results[0]['embedding']
        except Exception:
            pass
        return None

    def find_match(self, target_embedding, threshold: float) -> tuple:
        """Compare embedding against all registered users' variants.

        Returns (user_id, name, distance) for the user with the closest variant
        below threshold. Distance is the minimum cosine distance across all
        variants of the matched user.
        """
        if target_embedding is None:
            return None, None, None

        min_dist = threshold
        matched_id = None
        matched_name = None
        target_vec = np.array(target_embedding, dtype=float).flatten()

        for u_id, info in self.get_embeddings().items():
            for _variant_key, frames in info.get('variants', {}).items():
                for stored in frames:
                    if stored is None:
                        continue
                    stored_vec = np.array(stored, dtype=float).flatten()
                    dist = distance.cosine(target_vec, stored_vec)
                    if dist < min_dist:
                        min_dist = dist
                        matched_id = u_id
                        matched_name = info['name']

        if matched_id is None:
            return None, None, None
        return matched_id, matched_name, min_dist
