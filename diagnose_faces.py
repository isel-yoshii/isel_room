"""Diagnose face-matching problems against the LIVE enrolled gallery.

    python diagnose_faces.py

Read-only. Run it on the lab server: a local snapshot will not reproduce a
problem caused by an enrolment that happened since.

Written for "the kiosk keeps identifying the same person" — each section prints
what it checks and what a bad result means.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

import numpy as np
from dotenv import load_dotenv
from scipy.spatial import distance

load_dotenv()

from backend.db import session_scope                    # noqa: E402
from backend.db.models import User                      # noqa: E402

AUTH_THRESHOLD = float(os.getenv('FACE_AUTH_THRESHOLD', '0.55'))
LOW_CONFIDENCE = float(os.getenv('LOW_CONFIDENCE_THRESHOLD', '0.40'))
MATCH_MARGIN   = float(os.getenv('FACE_MATCH_MARGIN', '0.10'))


def load_gallery():
    """[(user_id, name, variant, frame_index, vector)] for every stored frame;
    vector is None for a registered-but-never-enrolled member."""
    out = []
    with session_scope() as session:
        for u in session.query(User).order_by(User.user_id).all():
            stored = u.embedding
            if isinstance(stored, str):
                try:
                    stored = json.loads(stored)
                except ValueError:
                    stored = None
            if not stored:
                out.append((u.user_id, u.name, None, None, None))
                continue
            for variant, frames in stored.items():
                for i, f in enumerate(frames or []):
                    out.append((u.user_id, u.name, variant, i,
                                np.array(f, dtype=float).flatten()))
    return out


def main() -> None:
    rows = load_gallery()
    vectors = [r for r in rows if r[4] is not None]
    if not vectors:
        sys.exit('No enrolled faces found. Is DATABASE_URL pointing at the live database?')

    print(f'thresholds: auth<{AUTH_THRESHOLD}  low-confidence<{LOW_CONFIDENCE}  '
          f'ambiguity margin {MATCH_MARGIN}\n')

    print('== 1. Enrolled frames per person ==')
    per_user = Counter((uid, name) for uid, name, v, i, vec in vectors)
    never = [(uid, name) for uid, name, v, i, vec in rows if vec is None]
    for (uid, name), n in sorted(per_user.items(), key=lambda kv: -kv[1]):
        variants = sorted({v for u, nm, v, i, vec in vectors if u == uid})
        flag = '  <-- most frames' if n == max(per_user.values()) else ''
        print(f'  {uid:>3} {name:<20} {n} frame(s)  {",".join(variants)}{flag}')
    for uid, name in never:
        print(f'  {uid:>3} {name:<20} not enrolled')
    print()

    print('== 2. Closest DIFFERENT person to each stored frame ==')
    print('   (below the auth threshold = two enrolled people are confusable)')
    worst = []
    for uid, name, variant, idx, vec in vectors:
        others = [(distance.cosine(vec, o_vec), o_name)
                  for o_uid, o_name, o_v, o_i, o_vec in vectors
                  if o_uid != uid and o_vec is not None]
        if not others:
            continue
        d, who = min(others)
        worst.append((d, f'{name}/{variant}[{idx}]', who))
    worst.sort()
    for d, label, who in worst[:8]:
        alarm = '  *** BELOW THRESHOLD ***' if d < AUTH_THRESHOLD else ''
        print(f'  {d:.4f}  {label:<28} -> {who}{alarm}')
    print(f'  ... {len(worst)} frames total, closest cross-person distance {worst[0][0]:.4f}')
    if worst[0][0] >= AUTH_THRESHOLD:
        print('  OK: every enrolled person is well separated from every other.')
    print()

    print('== 3. Magnet check — mean distance from each frame to all other people ==')
    print('   (a much lower mean than its peers = that frame attracts everyone)')
    means = []
    for uid, name, variant, idx, vec in vectors:
        others = [distance.cosine(vec, o_vec)
                  for o_uid, o_n, o_v, o_i, o_vec in vectors
                  if o_uid != uid and o_vec is not None]
        if others:
            means.append((float(np.mean(others)), f'{name}/{variant}[{idx}]'))
    means.sort()
    overall = float(np.mean([m for m, _ in means]))
    sd = float(np.std([m for m, _ in means]))
    for m, label in means[:5]:
        z = (m - overall) / sd if sd else 0.0
        alarm = '  *** OUTLIER, INSPECT THIS ENROLMENT ***' if z < -2.5 else ''
        print(f'  {m:.4f}  (z={z:+.2f})  {label}{alarm}')
    print(f'  gallery mean {overall:.4f}, sd {sd:.4f}')
    print()

    print('== 4. Random probes — who a meaningless embedding gets reported as ==')
    rng = np.random.default_rng(0)
    dim = len(vectors[0][4])
    wins, dists, matched = Counter(), [], 0
    for _ in range(2000):
        probe = rng.normal(size=dim)
        best = {}
        for uid, name, v, i, vec in vectors:
            d = distance.cosine(probe, vec)
            if not np.isfinite(d):
                continue
            if uid not in best or d < best[uid][0]:
                best[uid] = (d, name)
        ranked = sorted((d, n) for d, n in best.values())
        wins[ranked[0][1]] += 1
        dists.append(ranked[0][0])
        if ranked[0][0] < AUTH_THRESHOLD:
            matched += 1
    for name, n in wins.most_common(5):
        print(f'  {name:<20} {n:>5}  {100 * n / 2000:5.1f}%  of nearest-neighbour wins')
    print(f'  closest-distance range {min(dists):.3f}..{max(dists):.3f}')
    print(f'  garbage probes that would MATCH (<{AUTH_THRESHOLD}): {matched}/2000')
    if matched:
        print('  *** A meaningless embedding can match somebody. Raise FACE_AUTH_THRESHOLD '
              'strictness (lower the number) or re-enrol the outlier above. ***')
    else:
        print('  OK: a garbage embedding matches nobody; failed scans report "not recognised".')

    print('\nIf sections 2-4 are all OK, the gallery is healthy and a wrong identification '
          'is happening at capture time, not at matching time. Check the kiosk log for '
          '"face: matched ..." lines — they record the distance and the runner-up for '
          'every scan.')


if __name__ == '__main__':
    main()
