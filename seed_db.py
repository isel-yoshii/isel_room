"""
seed_db.py — Wipe and repopulate isel_room.db with realistic mock data.

Run from the project root:
    python seed_db.py

What it creates:
  - 10 lab members (1 先生, 2 M2, 4 M1, 2 B4, 1 Intern — one without a face embedding)
  - ~60 days of session history with realistic lab hours
  - 3 members currently in the lab (status = True, open session)
  - Audit log entries covering registrations and attendance events
"""

import sys
import os
import json
import random
import math
from datetime import datetime, timedelta, time

# ── Make sure project root is on the path ─────────────────
sys.path.insert(0, os.path.dirname(__file__))

from isel.db import SessionLocal as SessionClass, init_db, engine, Base
from isel.db.models import User, Session as LabSession, AuditLog

# ── Reproducible randomness ────────────────────────────────
random.seed(42)


# ── Helpers ───────────────────────────────────────────────

def random_unit_vector(dim=512):
    """Random unit vector simulating an ArcFace embedding."""
    v = [random.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v]


def rand_time(start_h=9, end_h=21):
    """Random time within lab hours."""
    h = random.randint(start_h, end_h - 1)
    m = random.choice([0, 10, 15, 20, 30, 40, 45, 50])
    return time(h, m)


def make_sessions(user_id, days_back=62, today=None):
    """
    Generate realistic session history for one user over the past N days.
    - Skips ~30% of weekdays, ~70% of weekends
    - 1–3 sessions per active day (usually 1)
    - Session length 45 min – 5 h
    """
    if today is None:
        today = datetime.now().date()
    sessions = []
    for d in range(days_back, 0, -1):
        day = today - timedelta(days=d)
        is_weekend = day.weekday() >= 5

        skip_chance = 0.70 if is_weekend else 0.30
        if random.random() < skip_chance:
            continue

        n_sessions = random.choices([1, 2, 3], weights=[70, 22, 8])[0]
        hour_cursor = random.randint(9, 12)

        for _ in range(n_sessions):
            if hour_cursor >= 22:
                break
            in_time = datetime.combine(day, time(hour_cursor, random.choice([0, 15, 30, 45])))
            duration_mins = random.randint(45, 300)
            out_time = in_time + timedelta(minutes=duration_mins)
            if out_time.hour >= 23:
                out_time = out_time.replace(hour=22, minute=30)
            method = random.choices(['face', 'face', 'face', 'manual'], weights=[75, 10, 10, 5])[0]
            sessions.append((in_time, out_time, method))
            hour_cursor = out_time.hour + random.randint(0, 2)

    return sessions


# ── Member definitions ─────────────────────────────────────

MEMBERS = [
    # (name, user_type, has_face, currently_in_lab)
    ('Choi Eunjong',  '先生', True,  False),
    ('Okura',         'M2',   True,  False),
    ('Inoue',         'M2',   True,  True),
    ('Naimi',         'M1',   True,  True),
    ('Yoshii',        'M1',   True,  False),
    ('Tasaki',        'M1',   True,  False),
    ('Hashimoto',     'M1',   False, False),  # no face enrolled
    ('Yamamoto',      'B4',     True,  True),
    ('Yamaguchi',     'B4',     True,  False),
    ('Lee',           'Intern', True,  False),
]


# ── Wipe and rebuild ───────────────────────────────────────

def main():
    print("Dropping all tables...")
    Base.metadata.drop_all(engine)
    print("Recreating tables...")
    init_db()

    db = SessionClass()
    now = datetime.now()
    today = now.date()

    # ── 1. Create users ──────────────────────────────────
    users = []
    for name, utype, has_face, _ in MEMBERS:
        embedding = random_unit_vector() if has_face else None
        user = User(name=name, user_type=utype, embedding=embedding, status=False)
        db.add(user)
    db.flush()
    db.commit()

    users = db.query(User).order_by(User.user_id).all()
    print(f"Created {len(users)} users.")

    # ── 2. Audit log: REGISTER entries ───────────────────
    for i, user in enumerate(users):
        registered_at = now - timedelta(days=random.randint(65, 120))
        db.add(AuditLog(
            action_type='REGISTER',
            target_user_id=user.user_id,
            target_name=user.name,
            performed_by='admin',
            timestamp=registered_at,
        ))
    db.commit()

    # ── 3. Historical sessions ────────────────────────────
    total_sessions = 0
    for user, (_, _, _, currently_in) in zip(users, MEMBERS):
        session_data = make_sessions(user.user_id, days_back=62, today=today)
        for in_t, out_t, method in session_data:
            db.add(LabSession(
                user_id=user.user_id,
                checked_in_at=in_t,
                checked_out_at=out_t,
                check_in_method=method,
            ))
            db.add(AuditLog(
                action_type='CHECKIN' if method != 'manual' else 'MANUAL_CHECKIN',
                target_user_id=user.user_id,
                target_name=user.name,
                performed_by='kiosk',
                timestamp=in_t,
            ))
            db.add(AuditLog(
                action_type='CHECKOUT' if method != 'manual' else 'MANUAL_CHECKOUT',
                target_user_id=user.user_id,
                target_name=user.name,
                performed_by='kiosk',
                timestamp=out_t,
            ))
            total_sessions += 1

    db.commit()
    print(f"Created {total_sessions} historical sessions.")

    # ── 4. Current in-lab sessions (open, no checkout) ───
    in_lab_users = [u for u, (_, _, _, currently_in) in zip(users, MEMBERS) if currently_in]
    for user in in_lab_users:
        checkin_offset_mins = random.randint(30, 180)
        checked_in_at = now - timedelta(minutes=checkin_offset_mins)
        user.status = True
        db.add(LabSession(
            user_id=user.user_id,
            checked_in_at=checked_in_at,
            checked_out_at=None,
            check_in_method='face',
        ))
        db.add(AuditLog(
            action_type='CHECKIN',
            target_user_id=user.user_id,
            target_name=user.name,
            performed_by='kiosk',
            timestamp=checked_in_at,
        ))

    db.commit()
    print(f"{len(in_lab_users)} members currently in lab: {[u.name for u in in_lab_users]}")

    # ── 5. Summary ────────────────────────────────────────
    n_sessions  = db.query(LabSession).count()
    n_audit     = db.query(AuditLog).count()
    print(f"\nDone.")
    print(f"  users:     {db.query(User).count()}")
    print(f"  sessions:  {n_sessions}")
    print(f"  audit_log: {n_audit}")
    db.close()


if __name__ == '__main__':
    main()
