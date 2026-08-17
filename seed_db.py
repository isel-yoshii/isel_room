"""Drop and recreate the dev database with mock members and attendance history.

    python seed_db.py            # asks before dropping
    python seed_db.py --force    # no prompt (CI / scripted resets)

Deterministic: the same seed always produces the same data, so a bug you see in
the dashboard is reproducible for everyone on the team.

Faces are deliberately NOT seeded. Embeddings are 512-d ArcFace vectors that can
only come from a real scan, so every mock member has an empty embedding and the
kiosk will not recognise them — register yourself at the kiosk to test face auth.

Gotcha, and the reason this matches production: the `embedding` column is
SQLAlchemy `JSON`, so a Python `None` is stored as the JSON *string* `'null'`,
not as SQL NULL. Production `user_id 8` (registered, never enrolled) is stored
exactly this way. `WHERE embedding IS NULL` therefore matches nothing — filter
on `embedding = 'null'` in SQL, or check falsiness after decoding in Python.
"""
from __future__ import annotations

import os
import random
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

from isel.db import Base, engine, session_scope  # noqa: E402
from isel.db.models import AuditLog, LabSession, User  # noqa: E402

DAYS_OF_HISTORY = 60
SEED = 20260817

# (name, user_type, how often they show up, typical arrival hour)
MEMBERS = [
    ('田崎 先生',   '先生',     0.55, 10),
    ('佐藤 健太',   'PhD',      0.85, 10),
    ('鈴木 美咲',   'M2',       0.80, 11),
    ('高橋 大輔',   'M2',       0.70, 12),
    ('伊藤 さくら', 'M1',       0.75, 11),
    ('渡辺 陽平',   'M1',       0.65, 13),
    ('山本 結衣',   'M1',       0.60, 12),
    ('中村 蓮',     'B4',       0.70, 13),
    ('小林 遥',     'B4',       0.55, 14),
    ('加藤 悠真',   'B4',       0.45, 14),
    ('Nguyen Minh', 'Intern',   0.50, 13),
]


def _sessions_for(user_id: int, attendance_rate: float, arrival_hour: int, rng: random.Random,
                  today: datetime) -> list[LabSession]:
    """One member's sessions over the history window."""
    out = []
    for days_ago in range(DAYS_OF_HISTORY, 0, -1):
        day = today - timedelta(days=days_ago)
        # Weekends are quiet but not empty — thesis season is real.
        rate = attendance_rate * (0.25 if day.weekday() >= 5 else 1.0)
        if rng.random() > rate:
            continue

        check_in = day.replace(
            hour=max(7, min(20, arrival_hour + rng.randint(-1, 2))),
            minute=rng.randrange(0, 60), second=0, microsecond=0,
        )
        hours = rng.choice([1, 2, 3, 3, 4, 5, 6, 7, 8])
        check_out = check_in + timedelta(hours=hours, minutes=rng.randrange(0, 60))

        method = 'face' if rng.random() > 0.12 else 'manual'
        # DAY_RESET_HOUR is 22:00 JST: anything still open gets force-closed,
        # and the legacy code writes that into the check-IN method column.
        reset = day.replace(hour=22, minute=0, second=0, microsecond=0)
        if check_out > reset:
            check_out, method = reset, 'auto_checkout'

        out.append(LabSession(user_id=user_id, checked_in_at=check_in,
                              checked_out_at=check_out, check_in_method=method))
    return out


def main() -> None:
    if '--force' not in sys.argv:
        target = os.getenv('DATABASE_URL', 'sqlite:///isel_room.db')
        print(f'This DROPS every table in: {target}')
        if input('Type "yes" to continue: ').strip().lower() != 'yes':
            sys.exit('Aborted.')

    rng = random.Random(SEED)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    n_sessions = 0

    with session_scope() as db:
        for name, user_type, rate, hour in MEMBERS:
            user = User(name=name, user_type=user_type, embedding=None, status=False)
            db.add(user)
            db.flush()  # assigns user_id

            db.add(AuditLog(action_type='REGISTER', target_user_id=user.user_id,
                            target_name=name, performed_by='seed',
                            timestamp=today - timedelta(days=DAYS_OF_HISTORY)))

            sessions = _sessions_for(user.user_id, rate, hour, rng, today)
            db.add_all(sessions)
            n_sessions += len(sessions)

            for s in sessions:
                db.add(AuditLog(
                    action_type='AUTO_CHECKOUT' if s.check_in_method == 'auto_checkout'
                    else 'MANUAL_CHECKIN' if s.check_in_method == 'manual' else 'CHECKIN',
                    target_user_id=user.user_id, target_name=name,
                    performed_by='seed', timestamp=s.checked_in_at))

    print(f'Seeded {len(MEMBERS)} members and {n_sessions} sessions '
          f'over {DAYS_OF_HISTORY} days. No faces — register at the kiosk to test auth.')


if __name__ == '__main__':
    main()
