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
        # How much closer the winner must be than the runner-up identity.
        # A real match on a healthy gallery clears this by a mile (genuine
        # ~0.30 vs next person ~0.85), so it only bites on genuinely ambiguous
        # scans. Tune with FACE_MATCH_MARGIN; 0 disables the check.
        self.match_margin = match_margin

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
                    if confidence >= self.detect_confidence:
                        return face_data['embedding']
                # With enforce_detection=False DeepFace returns an embedding for
                # ANY image — a wall, a hand, an empty room — reporting
                # face_confidence 0.0. Without this filter those bogus vectors
                # went into the matcher and matched whoever was nearest.
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

        Ranking per *identity* rather than per stored vector matters: matching
        on the single nearest vector gives whoever enrolled the most frames the
        most chances to win. One person with five frames against everyone
        else's three wins ambiguous comparisons roughly in proportion to that
        count — which is what "it always says the same person" looks like.
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
                        # silently loses every comparison. Skip it explicitly.
                        if not np.isfinite(dist):
                            continue
                        if u_id not in best or dist < best[u_id][0]:
                            best[u_id] = (dist, info['name'])
        return sorted((d, uid, name) for uid, (d, name) in best.items())

    def _closest(self, targets: list, registered: dict, threshold: float) -> tuple:
        """Closest (user_id, name, distance), or (None, None, None).

        Rejects a match when the runner-up identity is within `match_margin` of
        the winner: if two people are near-equally close, the scan is ambiguous
        and guessing is worse than asking the person to try again.
        """
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
        """Decode base64 frames and return an embedding for each one with a face.

        Frames with no detectable face are dropped, so the result may be shorter
        than the input (or empty). `limit` caps how many frames are processed —
        registration keeps the first few, the kiosk uses the whole burst.
        """
        from isel.utils import decode_image

        out = []
        for b64 in (frames_b64[:limit] if limit else frames_b64):
            emb = self.extract_embedding(decode_image(b64), enforce=enforce)
            if emb is not None:
                out.append([float(v) for v in emb])
        return out

    def find_match(self, target_embedding, threshold: float) -> tuple:
        """Compare one embedding against all registered users' variants.

        Returns (user_id, name, distance) for the user with the closest variant
        below threshold. Distance is the minimum cosine distance across all
        variants of the matched user.
        """
        if target_embedding is None:
            return None, None, None
        return self._closest([target_embedding], self.get_embeddings(), threshold)

    def find_best_match(self, embeddings: list, threshold: float) -> tuple:
        """Compare each embedding against the registered set and return the closest match.

        Used by the kiosk to capture multiple frames per scan and pick the best one.
        Catches blink / motion-blur misses that a single-frame scan would drop.
        Returns (user_id, name, distance) of the best match across all frames,
        or (None, None, None) if no frame matches.
        """
        if not embeddings:
            return None, None, None
        return self._closest(embeddings, self.get_embeddings(), threshold)
