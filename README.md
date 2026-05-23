# ISEL Room — Lab Presence & Attendance System

A face-recognition-based check-in/check-out system for the Intelligent Software Engineering Lab (KIT). Members enter and leave the lab by scanning their face at a check-in terminal; admins get a live dashboard, monthly attendance stats, a points leaderboard, and an audit trail of every action.

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
│   │   └── admin.py        # /api/admin/promote, force-checkout, audit
│   ├── services/       # Business logic
│   │   ├── attendance.py
│   │   ├── users.py
│   │   ├── points.py
│   │   ├── stats.py
│   │   └── audit.py
│   ├── db/             # SQLAlchemy layer
│   │   ├── __init__.py     # engine, SessionLocal, init_db()
│   │   ├── models.py       # User, Session, AuditLog
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
    │   ├── checkin.css     # Check-in screen styles
    │   └── dashboard.css   # Dashboard styles
    └── js/
        ├── core/           # api.js, camera.js, clock.js, nav.js, utils.js
        ├── checkin/        # state-machine.js, manual-picker.js,
        │                   # presence-strip.js, index.js
        └── dashboard/      # overview.js, attendance.js, admin.js,
                            # modals.js, index.js
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
| performed_by | VARCHAR(50) | `admin` · `check-in` · `system` |
| timestamp | DATETIME | |

**Points are awarded automatically:** 1 point per calendar day a member checked in (counted from the `sessions` table). No manual overrides.

---

## System Flow

### Check-in / Check-out

```
User faces camera
      │
      ▼
[Check-in screen captures frame as base64 JPEG]
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

`flask auto-checkout` force-closes all open `Session` rows, marks every user's `status = False`, and writes an `AUTO_CHECKOUT` AuditLog entry per affected user. Run nightly at the configured reset hour (default 10 PM).

Stale sessions (>24h with no checkout) are also closed lazily on the next check-in, so missing a single cron tick is non-catastrophic.

Promotions (B4→M1 / M1→M2 / M2→卒業 / M2→PhD / PhD→卒業) are no longer automatic. Use the **Members tab → Promote Students** wizard once a year to review and confirm each student's new role manually.

Sample crontab:

```
# crontab -e
0 22 * * *  cd /path/to/isel_room && FLASK_APP="app:create_app" flask auto-checkout
```

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

Three tabs accessible from the left sidebar (keyboard shortcuts `1` – `3`):

**Overview `[1]`**
- Stat cards: members currently in lab, unique check-ins today, total registered members
- 7-day check-in trend (line chart) and monthly activity hours (bar chart, top 8)
- Member grid — all members, present ones highlighted; click any card to open the profile modal
- Activity log with ← → date navigation

**Attendance `[2]`**
- Month navigator (← →)
- Points leaderboard — days present in the selected month, ranked 1st/2nd/3rd/…
- "All-Time" leaderboard — total days present across all months
- Session stats table — every member's session count, total time, average session length

**Admin `[3]`** — PIN required
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
| POST | `/api/admin/promote-students` | admin | Apply an explicit `{promotions: [{user_id, new_type}, ...]}` batch |

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
- A webcam (for check-in use)
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
| `FLASK_SECRET_KEY` | **required** | Random secret for Flask sessions — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_PIN` | **required** | PIN for the admin dashboard (any length) |
| `DATABASE_URL` | `sqlite:///isel_room.db` | SQLAlchemy DB URL; swap for MySQL in production |
| `SLACK_BOT_TOKEN` | — | Slack bot token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | — | Slack app token for Socket Mode (`xapp-...`) |
| `LOW_CONFIDENCE_THRESHOLD` | `0.40` | Cosine distance above which a face match is flagged as low-confidence |
| `DAY_RESET_HOUR` | `22` | Hour (0–23) at which the daily auto-checkout runs (lab closing time) |

> **Production note:** the app refuses to start if `FLASK_SECRET_KEY` is unset or left as the default `change-me-to-a-random-string`.

### Run (development)

```bash
# First time — seed the database with mock data
python seed_db.py

# Start the dev server
flask --app app run --host 0.0.0.0 --port 5001
```

Open `http://localhost:5001` in a browser — the Check-in screen loads by default. Switch to the Dashboard with the `D` key or the top-right nav link.

> **Production:** use `wsgi.py` with gunicorn. The auto-checkout daemon and Slack listener start automatically via `wsgi.py`; in dev they start only once (Werkzeug reloader guard is in place).

### Run tests

```bash
python -m pytest
```

### Seed / reset the database

```bash
python seed_db.py
```

Wipes and recreates the DB with 10 mock members (Choi Eunjong 先生, Okura/Inoue M2, Naimi/Yoshii/Tasaki/Hashimoto M1, Yamamoto/Yamaguchi B4, Lee Intern), ~60 days of session history, and 3 members currently in lab. Safe to re-run any time during development.

---

## Slack Integration

When `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` are set, the bot:
- Posts to `#a-lab-status` on every check-in/check-out
- Replies with the current member list when a message matches `在室`, `メンバー`, `だれ`, or `誰`

To enable: create a Slack app with Socket Mode enabled, add the tokens to `.env`, and invite the bot to `#a-lab-status`.
