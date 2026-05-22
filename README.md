# ISEL Room — Lab Presence & Attendance System

A face-recognition-based check-in/check-out system for the Intelligent Software Engineering Lab (KIT). Members enter and leave the lab by scanning their face at a kiosk terminal; admins get a live dashboard, monthly attendance stats, a points leaderboard, and an audit trail of every action.

---

## Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Language | Python | 3.10+ |
| Web framework | Flask | 3.x |
| ORM | SQLAlchemy | 2.0 |
| Database | SQLite (dev) / MySQL-compatible | — |
| Face recognition | DeepFace — ArcFace model | latest |
| Image processing | OpenCV | 4.13 |
| Vector math | NumPy + SciPy (cosine distance) | 2.4 / 1.17 |
| Frontend | Vanilla JavaScript (ES2020+) | — |
| Charts | Chart.js | 4.4 |
| Fonts | Syne, Nunito, IBM Plex Mono | Google Fonts |
| Slack | Slack Bolt (Socket Mode) | latest |
| Environment | python-dotenv | latest |

---

## Project Structure

```
isel_room/
├── app.py              # Flask app factory (create_app)
├── wsgi.py             # Production entry point
├── config.py           # Config classes (Dev/Prod/Test)
├── seed_db.py          # Populate DB with realistic mock data
├── requirements.txt
├── .env.example        # Template — copy to .env and fill in
│
├── isel/
│   ├── api/            # Flask blueprints (28 API endpoints)
│   │   ├── auth.py         # /api/admin/login|logout|status
│   │   ├── checkin.py      # /api/auth, /api/toggle
│   │   ├── users.py        # /api/users, /api/user/*, /api/register
│   │   ├── sessions.py     # /api/session/<id>
│   │   ├── presence.py     # /api/present, /api/present-detailed
│   │   ├── stats.py        # /api/stats/*, /api/log/*, /api/export/csv
│   │   └── admin.py        # /api/admin/promote, points/adjust, force-checkout, audit
│   ├── services/       # Business logic
│   │   ├── attendance.py
│   │   ├── users.py
│   │   ├── points.py
│   │   ├── stats.py
│   │   └── audit.py
│   ├── db/             # SQLAlchemy layer
│   │   ├── __init__.py     # engine, SessionLocal, init_db()
│   │   ├── models.py       # User, Session, AuditLog, PointAdjustment
│   │   └── repositories/   # user, session, audit, points repos
│   ├── face_engine.py  # DeepFace ArcFace wrapper
│   ├── integrations/
│   │   └── slack.py    # Slack Bolt app + send_slack_message()
│   ├── jobs/
│   │   └── auto_checkout.py  # Daily checkout daemon + April promotion
│   └── utils/
│       ├── admin_auth.py   # @admin_required decorator
│       └── image.py        # decode_image() helper
│
├── tests/              # pytest suite (16 tests)
│   ├── conftest.py
│   ├── test_attendance.py
│   ├── test_points.py
│   ├── test_users.py
│   └── test_api_checkin.py
│
└── ui/
    ├── index.html
    ├── img/
    │   └── logo.png        # ISEL brand logo (transparent PNG)
    ├── css/
    │   ├── tokens.css      # CSS variables only
    │   ├── base.css        # Reset, topbar, modals, shared buttons
    │   ├── checkin.css     # Kiosk-specific styles
    │   └── dashboard.css   # Dashboard styles
    └── js/
        ├── core/           # api.js, camera.js, clock.js, nav.js
        ├── checkin/        # state-machine.js, manual-picker.js,
        │                   # presence-strip.js, index.js
        └── dashboard/      # overview.js, statistics.js, points.js,
                            # admin.js, modals.js, index.js
```

---

## Database Schema

### `users`
| Column | Type | Notes |
|---|---|---|
| user_id | INT PK | auto-increment |
| name | VARCHAR(255) | display name |
| user_type | VARCHAR(50) | `先生` · `B4` · `M1` · `M2` · `Intern` · `卒業` |
| embedding | JSON | 512-dim ArcFace float array |
| status | BOOL | `True` = currently in lab |

### `sessions`
| Column | Type | Notes |
|---|---|---|
| id | INT PK | auto-increment |
| user_id | INT FK | → users |
| checked_in_at | DATETIME | entry timestamp |
| checked_out_at | DATETIME | exit timestamp; NULL = still in lab |
| check_in_method | VARCHAR(20) | `face` · `manual` · `auto_checkout` |

### `audit_log`
| Column | Type | Notes |
|---|---|---|
| id | INT PK | auto-increment |
| action_type | VARCHAR(30) | `REGISTER` `DELETE` `CHECKIN` `CHECKOUT` `MANUAL_CHECKIN` `MANUAL_CHECKOUT` `AUTO_CHECKOUT` `FORCE_CHECKOUT` `PROMOTE` |
| target_user_id | INT | user affected |
| target_name | VARCHAR(255) | name at time of action |
| performed_by | VARCHAR(50) | `admin` · `kiosk` · `system` |
| timestamp | DATETIME | |

### `point_adjustments`
| Column | Type | Notes |
|---|---|---|
| id | INT PK | auto-increment |
| user_id | INT FK | → users |
| delta | INT | positive = bonus point, negative = penalty |
| note | VARCHAR(255) | optional admin note |
| performed_by | VARCHAR(50) | always `admin` |
| timestamp | DATETIME | |

Points shown in the UI = auto-calculated days present + sum of all delta rows for that user.

---

## System Flow

### Check-in / Check-out

```
User faces camera
      │
      ▼
[Kiosk captures frame as base64 JPEG]
      │
      ▼
POST /api/auth
  └─ FaceEngine.extract_embedding()     ← DeepFace ArcFace, 512-dim vector
  └─ FaceEngine.find_match()            ← cosine distance vs all stored embeddings
        │
        ├─ distance < 0.40 ──────────────► match confirmed → show name + predicted event
        │
        ├─ 0.40 ≤ distance < 0.50 ──────► low confidence → show fail state (Space to pick manually)
        │
        └─ distance ≥ 0.50 ─────────────► no match → fail state
                                                            │
User confirms (↵) or picks manually (Space) ◄──────────────┘
      │
      ▼
POST /api/toggle
  └─ AttendanceService.toggle_entry()
        ├─ status=False → set status=True, open Session row
        └─ status=True  → set status=False, close Session row (set checked_out_at)
  └─ AuditLog entry written
  └─ Slack notification sent (if configured)
```

### User Registration

```
Admin opens Add Member modal (admin PIN required)
      │
      ▼
Enter name + role → look at camera → click Capture & Register
      │
      ▼
POST /api/register
  └─ extract_embedding(enforce=True)    ← must detect a clear face
  └─ duplicate check (cosine distance vs existing embeddings)
  └─ store User row with embedding as JSON array
  └─ AuditLog entry: REGISTER
```

### Daily Auto-Checkout

A daemon thread runs continuously, sleeping until the configured reset hour (default 4 AM). At that time it force-closes all open `Session` rows and marks every user's `status = False`. AuditLog entries with `AUTO_CHECKOUT` are written for each affected user.

---

## UI Screens

### Check-in Screen

The full-screen terminal view. Camera feed is always live. States cycle automatically:

| State | Description |
|---|---|
| `idle` | Waiting — press `Enter` or click Scan Face |
| `scanning` | Frame captured, ArcFace running |
| `confirmation` | Matched name shown; press `Enter` to confirm or `Esc` to cancel |
| `fail` | Face not recognised; press `Space` to open manual picker |
| `success` | Result displayed for 3 s, then resets to idle |

**Keyboard shortcuts:**

| Key | Action |
|---|---|
| `Enter` | Scan face / confirm pending action |
| `Space` | Open manual member picker |
| `Esc` | Cancel pending action |
| `C` | Switch to Check-in screen (global) |
| `D` | Switch to Dashboard (global) |

The **bottom presence strip** shows every registered member — in-lab members (green dot) sorted first, out-of-lab members (grey, dimmed) sorted alphabetically after.

---

### Dashboard

Four tabs accessible from the left sidebar (keyboard shortcuts `1` – `4`):

**Overview `[1]`**
- Stat cards: members currently in lab, unique check-ins today, total registered members
- 7-day check-in trend (line chart) and monthly activity hours (bar chart, top 8)
- Member grid — all members, present ones highlighted; click any card to open the profile modal
- Activity log with ← → date navigation

**Statistics `[2]`**
- Month navigator (← →)
- Table: every member's session count, total time, average session length for the selected month

**Points `[3]`**
- "This Month" leaderboard — days present in the selected month, ranked 1st/2nd/3rd/…
- "All-Time" leaderboard — total days present since the beginning + any admin-applied bonuses
- When admin is authenticated: `+` / `−` buttons on each row to apply a ±1 point adjustment (with optional note)

**Admin `[4]`** — PIN required
- Add Member button — opens registration modal (name, role, live camera)
- Member list with: role badge, face-enrolled status, in-lab indicator, Force Out, Edit (name/role), Re-Register Face (⊙), Delete
- Promote Students — batch-promotes `B4→M1`, `M1→M2`, `M2→卒業`
- Audit log — full append-only history of every admin action

---

## API Reference

### Auth & Admin

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/admin/login` | — | Authenticate with PIN; sets server-side session |
| POST | `/api/admin/logout` | admin | End admin session |
| GET | `/api/admin/status` | — | `{authenticated: bool}` |
| POST | `/api/admin/force-checkout/<user_id>` | admin | Force a user out |
| POST | `/api/admin/promote-students` | admin | Batch-promote all students one grade |
| POST | `/api/admin/points/adjust` | admin | Apply ±point bonus `{user_id, delta, note}` |

### Check-in / Check-out

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth` | Send base64 face image; returns `{matched, user_id, name, status, low_confidence}` |
| POST | `/api/toggle` | Toggle presence for `{user_id, check_in_method}`; returns `{name, event_type}` |

### Users

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/register` | admin | Register new user `{name, user_type, image}` |
| GET | `/api/users` | — | All users with `{id, name, type, status, has_face, last_seen}` |
| GET | `/api/user/<id>/profile` | — | Profile + recent 10 sessions + monthly stats |
| PUT | `/api/user/<id>` | admin | Update name/role `{name, user_type}` |
| DELETE | `/api/user/<id>` | admin | Delete user + all sessions |
| POST | `/api/user/<id>/face` | admin | Replace stored face embedding `{image}` |

### Sessions

| Method | Path | Auth | Description |
|---|---|---|---|
| PUT | `/api/session/<id>` | admin | Edit session times `{checked_in_at, checked_out_at}` |

### Presence

| Method | Path | Description |
|---|---|---|
| GET | `/api/present` | Names of members currently in lab |
| GET | `/api/present-detailed` | Names + duration since check-in |

### Logs & Stats

| Method | Path | Description |
|---|---|---|
| GET | `/api/log/today` | Today's check-in/out events |
| GET | `/api/log?date=YYYY-MM-DD` | Events for a specific date |
| GET | `/api/audit/log` | Full admin audit log |
| GET | `/api/stats/today` | `{unique_checkins}` for today |
| GET | `/api/stats/weekly` | Check-in counts for past 7 days |
| GET | `/api/stats/monthly?year=&month=` | Per-user sessions + total minutes |
| GET | `/api/stats/points?year=&month=` | Monthly point ranking (days present + bonuses) |
| GET | `/api/stats/points/total` | All-time point ranking |
| GET | `/api/export/csv?year=&month=` | Download monthly attendance CSV (admin) |

---

## Setup

### Prerequisites

- Python 3.10+
- A webcam (for kiosk use)
- (Optional) Slack app credentials for notifications

### Install

```bash
git clone https://github.com/your-org/isel_room.git
cd isel_room
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Configure

Copy `.env.example` to `.env` and fill in the required values:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `ADMIN_PIN` | required | 6–8 digit PIN for admin access |
| `FLASK_SECRET_KEY` | required | Flask session signing key |
| `DATABASE_URL` | `sqlite:///isel_room.db` | SQLAlchemy DB URL; swap for MySQL in production |
| `SLACK_BOT_TOKEN` | — | Slack bot token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | — | Slack app token for Socket Mode (`xapp-...`) |
| `LOW_CONFIDENCE_THRESHOLD` | `0.40` | Distance above which a match is flagged as low-confidence |
| `DAY_RESET_HOUR` | `4` | Hour (0–23) at which daily auto-checkout runs |

### Run

```bash
flask --app app run --host 0.0.0.0 --port 5001
```

The app starts on `http://0.0.0.0:5001`. Open it in a browser — the Check-in screen loads by default.

> The background auto-checkout daemon and Slack listener are started automatically when running via `wsgi.py` in production (e.g. with gunicorn). For development, invoke them via `isel.jobs.auto_checkout` and `isel.integrations.slack` if needed.

### Run tests

```bash
python -m pytest
```

### Seed test data (optional)

```bash
python seed_db.py
```

Creates 7 members (1 先生, 6 students across B4/M1/M2), ~60 days of session history with realistic attendance patterns, and 3 members currently marked as in-lab.

---

## Slack Integration

When `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` are set, the bot:
- Posts to `#a-lab-status` on every check-in/check-out
- Replies with the current member list when a message matches `在室`, `メンバー`, `だれ`, or `誰`

To enable: create a Slack app with Socket Mode enabled, add the tokens to `.env`, and invite the bot to `#a-lab-status`.
