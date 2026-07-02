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
        """Extract ArcFace embedding from an OpenCV frame. Returns None if no face found.

        We use detector_backend='retinaface' instead of DeepFace's default ('opencv').
        Retinaface is the gold standard for face localisation: significantly better at
        finding faces under varied lighting, head pose, and occlusion. First call after
        app start triggers a one-time ~50 MB model download.
        """
        try:
            results = DeepFace.represent(
                frame,
                model_name='ArcFace',
                detector_backend='retinaface',
                enforce_detection=enforce,
                align=True,
            )
            if results:
                for face_data in results:
                    confidence = face_data.get('face_confidence', 0.0)
                    if confidence >= 0.90:
                        return face_data['embedding']
                return None
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

    def find_best_match(self, embeddings: list, threshold: float) -> tuple:
        """Compare each embedding against the registered set and return the closest match.

        Used by the kiosk to capture multiple frames per scan and pick the best one.
        Catches blink / motion-blur misses that a single-frame scan would drop.
        Returns (user_id, name, distance) of the best match across all frames,
        or (None, None, None) if no frame matches.

        Fetches the registered embeddings once and reuses them across all input
        frames (vs. calling find_match in a loop, which re-fetches each time).
        """
        if not embeddings:
            return None, None, None

        registered = self.get_embeddings()
        min_dist = threshold
        matched_id = None
        matched_name = None

        for target_emb in embeddings:
            if target_emb is None:
                continue
            target_vec = np.array(target_emb, dtype=float).flatten()
            for u_id, info in registered.items():
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
