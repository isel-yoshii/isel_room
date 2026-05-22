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
isel_room/                        ← project root (~4 600 lines total)
│
├── server.py                     # 377 lines — Flask app: all 28 API routes + background threads
├── seed_db.py                    # 197 lines — populate DB with realistic test data
├── requirements.txt              # Python dependencies
├── .env                          # secrets + config (not committed)
│
├── core/                         # backend logic
│   ├── face_engine.py            #  45 lines — DeepFace wrapper (extract embedding, cosine match)
│   ├── database.py               # 699 lines — SQLDatabase: high-level interface used by server.py
│   ├── slack_bot.py              #  61 lines — Slack notification sender + presence query bot
│   └── SQL/
│       ├── sql_db.py             #  17 lines — SQLAlchemy engine + init_db()
│       ├── models/
│       │   └── model.py          #  45 lines — ORM models: User, Session, AuditLog, PointAdjustment
│       ├── repositories/
│       │   └── repository.py     #  33 lines — UserRepository (raw DB queries)
│       └── Services/
│           ├── AttendanceService.py  # 70 lines — toggle_entry(), session open/close, audit log
│           └── UserService.py        # 28 lines — add_user(), duplicate-face check
│
└── ui/                           # single-page frontend
    ├── index.html                # 408 lines — SPA shell: all screens, modals, boot script
    ├── app.js                    #  93 lines — shared utils: camera, API helpers, clock, nav
    ├── checkin.js                # 352 lines — Check-in screen state machine (idle→scan→confirm→result)
    ├── dashboard.js              # 1005 lines — all dashboard tabs: overview, stats, points, admin
    ├── style.css                 # 270 lines — global styles, design tokens, topbar, modals
    ├── checkin.css               # 318 lines — kiosk-specific styles: cam feed, face box, strip
    └── dashboard.css             # 569 lines — dashboard styles: grids, charts, tables, admin panel
```

---

## What Each File Does

### `server.py` — 377 lines
The entire Flask application. Handles all HTTP routing, background threads (daily auto-checkout scheduler, Slack thread), admin session management, and wires together `FaceEngine` and `SQLDatabase`. Every API endpoint lives here.

### `core/database.py` — 699 lines
The single database interface the rest of the app calls. Wraps SQLAlchemy sessions and the repository/service layer into plain Python methods. Contains logic for: user CRUD, presence toggling, session history, monthly/weekly stats, points calculations (monthly + all-time with manual bonus support), audit log, and CSV export.

### `core/face_engine.py` — 45 lines
A thin wrapper around DeepFace. `extract_embedding()` runs ArcFace on a JPEG frame and returns a 512-dimensional float vector. `find_match()` iterates over all stored embeddings and returns the closest user by cosine distance.

### `core/slack_bot.py` — 61 lines
Initialises a Slack Bolt app (if credentials are present). `send_slack_message()` is called by server.py on every check-in/out. Also registers a message handler that replies to presence queries in Japanese (在室, メンバー, だれ, 誰).

### `core/SQL/sql_db.py` — 17 lines
Creates the SQLAlchemy engine pointing at `isel_room.db` (SQLite). `init_db()` calls `create_all()` to create tables that do not yet exist — safe to call on every startup.

### `core/SQL/models/model.py` — 45 lines
Four ORM table definitions:
- `User` — registered members with face embedding
- `Session` — each lab visit (check-in → check-out pair)
- `AuditLog` — append-only record of every admin action
- `PointAdjustment` — manual ±point bonuses applied by admin

### `core/SQL/repositories/repository.py` — 33 lines
`UserRepository`: raw SQLAlchemy queries for `User` rows (get by ID, get all, get embedding table, add, delete).

### `core/SQL/Services/AttendanceService.py` — 70 lines
`AttendanceService.toggle_entry()` flips a user's `status`, opens or closes a `Session` row, and writes an `AuditLog` entry. The core transaction for every check-in/out event.

### `core/SQL/Services/UserService.py` — 28 lines
`UserService.add_user()` creates a `User` row and writes a REGISTER audit log entry.

---

### `ui/index.html` — 408 lines
The single HTML file. Contains the topbar, the Check-in screen, the Dashboard screen (with sidebar), and all modal overlays (registration, face re-registration, manual picker, PIN, profile). Loads Chart.js from CDN, then the three JS files in order, then runs the boot script.

### `ui/app.js` — 93 lines
Shared utilities loaded before any screen-specific code:
- `startCamera` / `stopCamera` / `captureFrame` — WebRTC camera helpers
- `api.get` / `api.post` — fetch wrappers that parse JSON
- `tick()` — live clock (date + day + time) updated every second
- `switchScreen()` — toggles between Check-in and Dashboard
- Global keyboard shortcuts: `C` → Check-in screen, `D` → Dashboard

### `ui/checkin.js` — 352 lines
The Check-in screen is a state machine with five named states: `idle`, `scanning`, `confirmation`, `fail`, `success`. Each state has its own tag colour, button label, and hint row. Handles `scanFace()` (POST to `/api/auth`), `commitToggle()` (POST to `/api/toggle`), the manual member picker modal, and the bottom presence strip.

### `ui/dashboard.js` — 1005 lines
All four dashboard tabs in one file:
- **Overview** — fetches present users, member list, today's log, weekly/monthly chart data, renders the member grid and activity log
- **Statistics** — monthly attendance table (sessions, total time, avg per session)
- **Points** — dual leaderboard: "This Month" and "All-Time", with admin ±1 adjustment buttons
- **Admin** — member list with edit/face-rereg/delete actions, registration modal, audit log, session editing inside the profile modal
- PIN modal, profile modal, session editing, user promotion

### `ui/style.css` — 270 lines
Global design tokens (CSS variables for colours, radii, shadows), topbar, screen switcher buttons, keyboard badges, modal overlay, clock, live dot.

### `ui/checkin.css` — 318 lines
Kiosk-only styles: camera feed box, face detection corners, scan-line animation, state panel, result card, event badge, hint row, bottom member strip.

### `ui/dashboard.css` — 569 lines
Dashboard styles: sidebar, member grid cards, stat cards, chart containers, log rows, stats table, points table with rank colours, admin user rows, edit forms, profile modal.

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

Create `.env` in the project root:

```env
ADMIN_PIN=123456
FLASK_SECRET_KEY=change-me-in-production

# Optional: Slack integration
# SLACK_BOT_TOKEN=xoxb-...
# SLACK_APP_TOKEN=xapp-...

# Optional overrides
# LOW_CONFIDENCE_THRESHOLD=0.40
# DAY_RESET_HOUR=4
```

| Variable | Default | Description |
|---|---|---|
| `ADMIN_PIN` | required | 6–8 digit PIN for admin access |
| `FLASK_SECRET_KEY` | required | Flask session signing key |
| `SLACK_BOT_TOKEN` | — | Slack bot token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | — | Slack app token for Socket Mode (`xapp-...`) |
| `LOW_CONFIDENCE_THRESHOLD` | `0.40` | Distance above which a match is flagged as low-confidence |
| `DAY_RESET_HOUR` | `4` | Hour (0–23) at which daily auto-checkout runs |

### Run

```bash
python server.py
```

The app starts on `http://0.0.0.0:5001`. Open it in a browser — the Check-in screen loads by default.


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
