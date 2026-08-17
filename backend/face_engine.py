from __future__ import annotations
import logging
import numpy as np
from deepface import DeepFace
from scipy.spatial import distance

logger = logging.getLogger(__name__)


class FaceEngine:
    def __init__(self, get_embeddings, auth_threshold: float = 0.55, reg_threshold: float = 0.50,
                 match_margin: float = 0.10, detect_confidence: float = 0.90) -> None:
        self.get_embeddings = get_embeddings
        self.auth_threshold = auth_threshold
        self.reg_threshold = reg_threshold
        self.detect_confidence = detect_confidence
        # How much closer the winner must be than the runner-up identity. A real
        # match clears it easily (~0.30 vs ~0.85); 0 disables the check.
        self.match_margin = match_margin

    def extract_embedding(self, frame, enforce: bool = True):
        """None if no face found. retinaface (not DeepFace's default 'opencv')
        handles our lighting and head-pose spread; first call downloads ~50 MB."""
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
                    if confidence >= self.detect_confidence:
                        return face_data['embedding']
                # With enforce_detection=False DeepFace returns an embedding for
                # ANY image (a wall, a hand) at face_confidence 0.0. Unfiltered,
                # those bogus vectors matched whoever was nearest.
                logger.info('face: detection rejected, best confidence %.2f < %.2f',
                            max(f.get('face_confidence', 0.0) for f in results),
                            self.detect_confidence)
                return None
        except Exception:
            pass
        return None

    @staticmethod
    def _rank(targets: list, registered: dict) -> list[tuple[float, int, str]]:
        """Each registered identity's best distance to any target, closest first.

        Per *identity*, not per stored vector: ranking vectors gives whoever
        enrolled the most frames the most chances to win, which is what "it
        always says the same person" looks like.
        """
        best: dict[int, tuple[float, str]] = {}
        for target in targets:
            if target is None:
                continue
            target_vec = np.array(target, dtype=float).flatten()
            for u_id, info in registered.items():
                for _variant_key, frames in info.get('variants', {}).items():
                    for stored in frames:
                        if stored is None:
                            continue
                        stored_vec = np.array(stored, dtype=float).flatten()
                        dist = distance.cosine(target_vec, stored_vec)
                        # A zero or malformed stored vector yields nan, which
                        # compares false against everything. Skip it explicitly.
                        if not np.isfinite(dist):
                            continue
                        if u_id not in best or dist < best[u_id][0]:
                            best[u_id] = (dist, info['name'])
        return sorted((d, uid, name) for uid, (d, name) in best.items())

    def _closest(self, targets: list, registered: dict, threshold: float) -> tuple:
        """Closest (user_id, name, distance), or (None, None, None) — including
        when the runner-up is within match_margin, where guessing is worse than
        asking the person to scan again."""
        ranked = self._rank(targets, registered)
        if not ranked:
            return None, None, None

        dist, u_id, name = ranked[0]
        if dist >= threshold:
            logger.info('face: no match (closest %s at %.3f, threshold %.2f)', name, dist, threshold)
            return None, None, None

        if len(ranked) > 1:
            runner_dist, _, runner_name = ranked[1]
            if runner_dist - dist < self.match_margin:
                logger.warning(
                    'face: AMBIGUOUS, rejected — %s at %.3f vs %s at %.3f (margin %.3f < %.3f)',
                    name, dist, runner_name, runner_dist, runner_dist - dist, self.match_margin)
                return None, None, None
            logger.info('face: matched %s at %.3f (runner-up %s at %.3f)',
                        name, dist, runner_name, runner_dist)
        else:
            logger.info('face: matched %s at %.3f (only registered identity)', name, dist)

        return u_id, name, dist

    def embeddings_from_frames(self, frames_b64: list, limit: int | None = None,
                               enforce: bool = True) -> list[list[float]]:
        """Frames with no detectable face are dropped, so the result may be
        shorter than the input, or empty."""
        from backend.utils import decode_image

        out = []
        for b64 in (frames_b64[:limit] if limit else frames_b64):
            emb = self.extract_embedding(decode_image(b64), enforce=enforce)
            if emb is not None:
                out.append([float(v) for v in emb])
        return out

    def find_match(self, target_embedding, threshold: float) -> tuple:
        if target_embedding is None:
            return None, None, None
        return self._closest([target_embedding], self.get_embeddings(), threshold)

    def find_best_match(self, embeddings: list, threshold: float) -> tuple:
        if not embeddings:
            return None, None, None
        return self._closest(embeddings, self.get_embeddings(), threshold)
