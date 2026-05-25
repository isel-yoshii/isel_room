"""
seed_db.py — Wipe and repopulate isel_room.db with the real lab roster.

Run from the project root:
    python seed_db.py

What it creates:
  - 10 lab members, no face embeddings, no session history
  - All members start with status=False (not in lab)
  - Register faces via the Members tab after running this

WARNING: drops and recreates all tables. Do not run on a live database.
"""

import sys
import os
from datetime import datetime, timedelta
import random

# ── Make sure project root is on the path ─────────────────
sys.path.insert(0, os.path.dirname(__file__))

from isel.db import SessionLocal as SessionClass, init_db, engine, Base
from isel.db.models import User, AuditLog

# ── Member definitions ─────────────────────────────────────
# (display_name, user_type)
MEMBERS = [
    ('Choi',        '先生'),
    ('R.Okura',     'M2'),
    ('T.Inoue',     'M2'),
    ('Naimi',       'M1'),
    ('Y.Yoshii',    'M1'),
    ('H.Hashimoto', 'M1'),
    ('Y.Tasaki',    'M1'),
    ('Yamamoto',    'B4'),
    ('Yamaguchi',   'B4'),
    ('Lee',         'Intern'),
]


# ── Wipe and rebuild ───────────────────────────────────────

def main():
    print("Dropping all tables...")
    Base.metadata.drop_all(engine)
    print("Recreating tables...")
    init_db()

    db = SessionClass()
    now = datetime.now()

    # ── Create users (no embeddings — register faces via the UI) ──
    for name, utype in MEMBERS:
        db.add(User(name=name, user_type=utype, embedding=None, status=False))
    db.flush()
    db.commit()

    users = db.query(User).order_by(User.user_id).all()
    print(f"Created {len(users)} users.")

    # ── Audit log: one REGISTER entry per member ───────────
    for user in users:
        registered_at = now - timedelta(days=random.randint(1, 7))
        db.add(AuditLog(
            action_type='REGISTER',
            target_user_id=user.user_id,
            target_name=user.name,
            performed_by='admin',
            timestamp=registered_at,
        ))
    db.commit()

    print(f"\nDone.")
    print(f"  users:     {db.query(User).count()}")
    print(f"  sessions:  0")
    print(f"  Next: register each member's face via the Members tab.")
    db.close()


if __name__ == '__main__':
    main()
