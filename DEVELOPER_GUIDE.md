# Developer Guide — ISEL 在室管理システム

> **For the next generation of maintainers.** This guide is the single source of truth for how the system is built, how to extend it, and the pitfalls you'd otherwise have to learn the hard way. Read it once cover-to-cover on your first day, then keep it open as a reference.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Overview](#2-system-overview)
3. [Repository Layout](#3-repository-layout)
4. [Backend Architecture](#4-backend-architecture)
5. [Face Recognition Pipeline](#5-face-recognition-pipeline)
6. [Frontend Architecture](#6-frontend-architecture)
7. [Configuration & Environments](#7-configuration--environments)
8. [Slack Integration](#8-slack-integration)
9. [Background Jobs](#9-background-jobs)
10. [Testing](#10-testing)
11. [Common Workflows (Recipes)](#11-common-workflows-recipes)
12. [Conventions & House Style](#12-conventions--house-style)
13. [Known Limitations & Future Work](#13-known-limitations--future-work)
14. [Troubleshooting](#14-troubleshooting)
15. [Getting Help](#15-getting-help)

---

## 1. Introduction

### Who this guide is for

You are a junior developer (B4 / M1 / Intern) who has just been handed this codebase to maintain and extend. You may be the only person actively working on it for months at a time. This guide assumes you know what programming is, but does **not** assume you've used Flask, SQLAlchemy, or DeepFace before.

### How to use this guide

- **First read (1–2 hours):** read sections 1–6 top to bottom. Skip code blocks on first pass — focus on the prose.
- **Second pass:** read with the codebase open. For each file mentioned, open it and read the first 20 lines.
- **Day-to-day:** treat sections 7–14 as a reference. Section 11 (recipes) is the most-used.
- **Before changing anything:** read section 12 (conventions). Diverging from house style is the fastest way to make this codebase hard to maintain.

### Prerequisites (and where to learn each)

| You should know | Where to learn (free) |
|---|---|
| Python 3 basics | [docs.python.org/3/tutorial](https://docs.python.org/3/tutorial/) |
| Flask (web framework) | [flask.palletsprojects.com/en/3.0.x/quickstart](https://flask.palletsprojects.com/en/3.0.x/quickstart/) |
| SQLAlchemy 2.0 (ORM) | [docs.sqlalchemy.org/en/20/tutorial](https://docs.sqlalchemy.org/en/20/tutorial/index.html) |
| Modern JavaScript (ES2020+) | [javascript.info](https://javascript.info/) |
| Git + conventional commits | [conventionalcommits.org](https://www.conventionalcommits.org/) |

You do **not** need to learn DeepFace internals — we wrap it in one file and you'll rarely touch it.

### Glossary

| Term | Meaning |
|---|---|
| `先生` (sensei) | Faculty / professor — the lab head |
| `学生` (gakusei) | Student — covers B4, M1, M2, PhD, Intern |
| `B4` | 4th-year undergraduate (final year before grad school) |
| `M1` / `M2` | 1st / 2nd year master's student |
| `PhD` | Doctoral student |
| `Intern` | Short-term researcher (not on the formal promotion path) |
| `卒業` (sotsugyō) | Graduated — terminal state, no longer active |
| `AY` / `年度` | Academic year (Apr 1 → Mar 31, Japanese system) |
| **Embedding** | A fixed-length vector summarising a face. We use 512 floats from ArcFace. |
| **Cosine distance** | A number ∈ [0, 2] measuring how different two vectors are. 0 = identical, 2 = opposite. We treat anything below 0.55 as "same person." |
| **Variant slot** | One of `normal` / `glasses` / `mask`. Each user can store up to 3 frames per slot (max 9 embeddings per user). |
| **Burst capture** | Snapping 3 frames in quick succession (~350 ms apart) to capture micro-pose variation. |

---

## 2. System Overview

### The problem

The ISEL lab wants to know, at any moment, **who is in the room**. They also want history (who comes in often? when?) and a paper trail (who let themselves in late on Sunday?).

We built a face-recognition turnstile: a tablet/laptop at the door runs a web page that watches the camera; when someone walks up, their face is matched against the member roster and a check-in event is recorded.

### What it is not

- Not a security gate. Anyone can walk past the camera. The system is for **tracking**, not enforcement.
- Not a time-clock for billable hours. Points = days present, not minutes worked.
- Not multi-lab. One install = one lab.

### Architecture at a glance

```
┌──────────────────────────────────────────────────────────┐
│  Browser (kiosk at door)              Browser (sensei)   │
│  ┌──────────────────────┐         ┌────────────────────┐ │
│  │  Check-in screen     │         │  Dashboard         │ │
│  │  (camera + state UI) │         │  (4 tabs, modals)  │ │
│  └────────┬─────────────┘         └────────┬───────────┘ │
└───────────┼───────────────────────────────┼─────────────┘
            │ HTTP (JSON)                   │
            ▼                               ▼
┌──────────────────────────────────────────────────────────┐
│                Flask app (app.py / wsgi.py)              │
│                                                          │
│   isel/api/         ◄── thin HTTP wrappers               │
│       │                                                  │
│       ▼                                                  │
│   isel/services/    ◄── all business logic               │
│       │                                                  │
│       ├──► isel/db/         SQLAlchemy + SQLite          │
│       ├──► isel/face_engine.py  DeepFace ArcFace         │
│       └──► isel/integrations/slack.py  status board      │
└──────────────────────────────────────────────────────────┘
```

### Two user surfaces

| Surface | URL | Audience | Default keyboard |
|---|---|---|---|
| Check-in screen | `/` (default) | Anyone walking up to the door | `Enter` scan · `Space` manual · `Esc` cancel |
| Dashboard | `/` then press `D` | Sensei + admins | `1`/`2`/`3`/`4` tabs · PIN gates admin tabs |

Both live in the same single-page app (`ui/index.html`). They're toggled via `switchScreen('check-in' | 'dashboard')` in [ui/js/core/nav.js](ui/js/core/nav.js).

### Lifecycle of one check-in

```
1. User stands at the camera, presses Enter (or just waits, then clicks Scan).
2. Browser captures one frame, base64-encodes it, POSTs to /api/auth.
3. Server: face_engine.extract_embedding() — DeepFace runs ArcFace, returns 512 floats.
4. Server: face_engine.find_match() — cosine-distance vs every stored variant of every user;
   picks the min; if min < 0.55, returns the user_id + name.
5. Server replies { matched: true, user_id, name, status, low_confidence }
   and stashes a 30-second pending_toggle token in the Flask session.
6. UI moves to "confirmation" state. User presses Enter to confirm.
7. Browser POSTs /api/toggle { user_id, check_in_method: 'face' }.
8. Server: attendance.toggle_entry() — flips User.status, opens/closes a Session row,
   writes an AuditLog row.
9. Server: integrations.slack.update_status_board() — edits the daily Slack message.
10. UI moves to "success" state, shows "Welcome, <name>!", then resets to idle.
```

---

## 3. Repository Layout

```
isel_room/
├── app.py                  # Flask app factory (create_app)
├── wsgi.py                 # Production entry point (create_app('prod'))
├── config.py               # Config classes: Dev / Prod / Test
├── seed_db.py              # Drop + recreate DB with mock data
├── requirements.txt
├── .env.example            # Template — copy to .env, fill in
├── slack_state.json        # (Runtime, gitignored) cached Slack msg timestamp
├── isel_room.db            # (Runtime, gitignored) SQLite database
│
├── isel/
│   ├── api/                # Flask blueprints — one file per resource
│   │   ├── __init__.py     # register_blueprints(app)
│   │   ├── auth.py         # POST /api/admin/login, /logout · GET /status
│   │   ├── checkin.py      # POST /api/auth, /api/toggle
│   │   ├── users.py        # GET/POST/PUT/DELETE /api/users + /face
│   │   ├── sessions.py     # PUT /api/session/<id>
│   │   ├── presence.py     # GET /api/present, /api/present-detailed
│   │   ├── stats.py        # /api/log, /api/stats/*, /api/export/csv
│   │   └── admin.py        # /api/audit/*, /api/admin/promote-students,
│   │                       # /api/stats/points*
│   ├── services/           # Business logic — pure Python
│   │   ├── attendance.py   # toggle_entry, auto_checkout_all
│   │   ├── users.py        # register, delete, face variants, promote
│   │   ├── points.py       # monthly + academic-year leaderboards
│   │   ├── stats.py        # weekly grid, monthly per-user, CSV export
│   │   └── audit.py        # record() + recent_entries() with filters
│   ├── db/                 # SQLAlchemy layer
│   │   ├── __init__.py     # engine, SessionLocal, init_db()
│   │   └── models.py       # User, Session, AuditLog
│   ├── face_engine.py      # DeepFace ArcFace wrapper (one class)
│   ├── integrations/
│   │   └── slack.py        # update_status_board() — single daily message
│   └── utils/
│       ├── __init__.py     # @admin_required decorator
│       └── image.py        # decode_image(), ImageDecodeError
│
├── tests/                  # pytest suite (~21 tests)
│   ├── conftest.py         # in-memory SQLite + shared fixtures
│   ├── test_attendance.py
│   ├── test_points.py
│   ├── test_users.py
│   ├── test_face_engine.py
│   └── test_api_checkin.py
│
└── ui/                     # Static frontend (no build step)
    ├── index.html          # Single-page shell — both screens live here
    ├── img/logo.png
    ├── css/
    │   ├── tokens.css      # CSS variables only (colors, spacing)
    │   ├── base.css        # Reset, topbar, modals, shared buttons
    │   ├── checkin.css     # Kiosk screen styles
    │   └── dashboard.css   # Dashboard styles (~900 lines, the biggest)
    └── js/
        ├── core/           # Generic helpers (api, camera, clock, nav, utils)
        ├── checkin/        # Kiosk-screen state machine + manual picker
        └── dashboard/      # Tabs: overview, attendance(+grid), members,
                            # activity, modals
```

### Where to add new code

- **New page/section in the UI?** Add markup to `ui/index.html`, add a JS module under `ui/js/dashboard/`, add `<script>` tag at the bottom of `index.html`.
- **New API endpoint?** Pick the right blueprint in `isel/api/`, or create a new one and register it in `isel/api/__init__.py`.
- **New business logic?** It goes in `isel/services/`. API code should never import models or build queries directly.
- **New DB column?** Edit `isel/db/models.py` and run `python seed_db.py` to recreate. We have no migration framework — at our scale, drop+seed is fine for dev.

---

## 4. Backend Architecture

### 4.1 The layering

```
HTTP request
   │
   ▼
isel/api/*.py     ──►  Parse request, call service, jsonify response.
   │                   No business logic. No SQL.
   ▼
isel/services/*.py ──►  All business logic. Pure Python.
   │                    Opens its own DB session via SessionLocal().
   ▼
isel/db/models.py ──►  SQLAlchemy ORM models.
```

**Iron rule:** API code never imports from `isel.db.models` and never runs queries directly. It always goes through a service function. This keeps the API thin and means we can swap Flask for FastAPI tomorrow with one folder's worth of changes.

The only exceptions are `isel/api/checkin.py` (uses `current_app.config['FACE_ENGINE']`) and `isel/api/users.py` (imports `VARIANT_KEYS` constant) — both legitimate because they need the constants, not the data.

### 4.2 App factory & startup

[app.py](app.py) defines `create_app(config_name)`. The startup order matters:

```python
def create_app(config_name: str = 'dev') -> Flask:
    cfg = get_config(config_name)                # Pick Config class
    app = Flask(__name__,
                template_folder='ui',
                static_folder='ui',
                static_url_path='/ui')
    app.config.from_object(cfg)
    app.config['TEMPLATES_AUTO_RELOAD'] = True   # Edit index.html → no restart
    app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB request cap

    @app.errorhandler(ImageDecodeError)          # Catch oversize images globally
    def _image_decode_error(err):
        return jsonify({'matched': False, 'success': False, 'message': str(err)}), 400

    from isel.db import init_db
    init_db()                                    # CREATE TABLE IF NOT EXISTS

    from isel.face_engine import FaceEngine
    from isel.services.users import get_all_embeddings
    app.config['FACE_ENGINE'] = FaceEngine(get_all_embeddings)
    # ^^^ Heavy! Loads DeepFace + TensorFlow into memory (~500 MB, ~10 s).
    #     Done ONCE per process. Never create FaceEngine per-request.

    from isel.api import register_blueprints
    register_blueprints(app)

    @app.cli.command('auto-checkout')            # `flask auto-checkout` CLI
    def _cli_auto_checkout():
        from isel.services.attendance import auto_checkout_all
        auto_checkout_all()

    @app.get('/')
    def index():
        return render_template('index.html')

    return app
```

**Production** uses [wsgi.py](wsgi.py) which calls `create_app('prod')` — and `ProdConfig.__init__` raises `RuntimeError` if `FLASK_SECRET_KEY` or `ADMIN_PIN` is missing. This is intentional. Don't bypass it; set the env vars.

### 4.3 Database models

[isel/db/models.py](isel/db/models.py) defines three tables. There are no migrations — we use `create_all` and drop/reseed for schema changes.

**`users`**

| Column | Type | Notes |
|---|---|---|
| `user_id` | INT PK | auto-increment |
| `name` | VARCHAR(255) | display name; indexed |
| `user_type` | VARCHAR(50) | one of `先生` · `PhD` · `M2` · `M1` · `B4` · `Intern` · `卒業` (free-text, not enforced) |
| `embedding` | JSON | face data — see [section 5.2](#52-the-3-variant-slot-system) for the shape |
| `status` | BOOLEAN | `True` = currently in lab |

**`sessions`**

| Column | Type | Notes |
|---|---|---|
| `id` | INT PK | auto-increment |
| `user_id` | INT FK → users | indexed |
| `checked_in_at` | DATETIME | indexed (powers date-window queries) |
| `checked_out_at` | DATETIME nullable | `NULL` = still in lab |
| `check_in_method` | VARCHAR(20) | `face` · `manual` · `auto_checkout` |

**`audit_log`**

| Column | Type | Notes |
|---|---|---|
| `id` | INT PK | auto-increment |
| `action_type` | VARCHAR(30) | `REGISTER` · `DELETE` · `CHECKIN` · `CHECKOUT` · `MANUAL_CHECKIN` · `MANUAL_CHECKOUT` · `AUTO_CHECKOUT` · `STALE_SESSION_CLOSED` · `PROMOTE` |
| `target_user_id` | INT | user affected (not a real FK — see below) |
| `target_name` | VARCHAR(255) | name snapshot at time of action |
| `performed_by` | VARCHAR(50) | `admin` · `check-in` · `system` |
| `timestamp` | DATETIME | indexed |

**Why `target_name` is denormalized on `audit_log`:** if you delete a user, their audit history must remain readable. Joining to `users` would break; storing the name at write-time is the simplest fix. The trade-off is renames don't propagate (you'll see the old name in old log entries), which is the correct behavior — history should reflect what was true at the time.

### 4.4 Services — per-file deep dive

#### `isel/services/users.py`

The biggest service file. Handles registration, CRUD, face variant storage, and promotions.

Key constants:
```python
VARIANT_KEYS = ('normal', 'glasses', 'mask')
MAX_FRAMES_PER_VARIANT = 3
```

Key functions:

- **`_as_variant_dict(stored)`** — Backward-compat normalizer. Reads `User.embedding` (which may be `None`, a flat list of floats (legacy single vector), a list of lists (older format), or a proper dict) and always returns `{variant_key: [vec, vec, vec]}`. **You should always go through this when reading embeddings.** Direct dict access will break on legacy rows. Note: `seed_db.py` deliberately writes legacy-shaped data (flat single vector) to exercise this path.

- **`register_user(name, user_type, variants) → int`** — Creates a `User` row. `variants` can be a dict, a flat list, or a single vector — all normalised through `_as_variant_dict`. Returns the new `user_id`.

- **`set_face_variant(user_id, variant_key, frames) → dict`** — Replaces one slot (e.g. just `glasses`) without touching the others. Caps at 3 frames. Returns `{success, variants: [...]}` listing which slots are now populated.

- **`get_all_embeddings() → dict`** — Powers `FaceEngine.find_match`. Returns `{user_id: {name, variants: {normal: [...], glasses: [...]}}}`. Called on every check-in (this is fine — we read it once per request and the queries are millisecond-scale).

- **`get_all_users_info() → list[dict]`** — Powers the Members tab. Returns per-user metadata including `face_variants: ['normal', 'glasses']` (which slots are populated). `last_seen` is the most recent `checked_out_at` of any session.

- **`promote_students(promotions) → dict`** — Applies an explicit list `[{user_id, new_type}, ...]`. All-or-nothing transaction. Writes `PROMOTE` audit rows. **Why explicit-only:** the user explicitly rejected automatic promotion chains because PhD branching makes them ambiguous (B4 can become M1 *or* graduate, M2 can become PhD *or* graduate). The frontend wizard ([ui/js/dashboard/modals.js](ui/js/dashboard/modals.js)) walks the admin through each student before submission.

#### `isel/services/attendance.py`

Toggle-based — check-in and check-out share one function.

- **`toggle_entry(user_id, check_in_method='face') → dict`** — If user is OUT, opens a new `Session` row + sets `status=True`. If IN, sets `status=False` + closes the open session. Always writes an `AuditLog` row with `performed_by='check-in'`. Returns `{user_id, name, event_type: 'IN' | 'OUT', timestamp}`.

- **`auto_checkout_all() → None`** — Closes all open sessions, marks status False on every present user, writes one `AUTO_CHECKOUT` audit row per user, then refreshes the Slack board. Called nightly via `flask auto-checkout` cron.

- **`_close_stale_session(session, user_id, now)`** — Internal safety net. If a session has been open >24h, it's almost certainly forgotten. Closes it lazily on the user's *next* check-in, writes a `STALE_SESSION_CLOSED` audit row. This means missing one cron tick is non-catastrophic.

- **`get_present_users_detailed() → list[dict]`** — Returns currently-present members with `{id, name, type, duration}` for the bottom presence strip.

#### `isel/services/points.py`

Pure SQL aggregations — no business logic to speak of. The rule: **1 point = 1 calendar day with at least one check-in.**

- **`current_academic_year(today=None) → int`** — Returns the AY containing today. `today.year` if month ≥ 4, else `today.year - 1`. AY 2026 means April 1, 2026 → March 31, 2027.

- **`monthly_leaderboard(year, month) → list[dict]`** — Ranks members by distinct days present in the calendar month.

- **`academic_year_leaderboard(ay_year) → list[dict]`** — Same, scoped to `[ay_year-04-01, (ay_year+1)-04-01)`. **Half-open interval** — Mar 31 belongs to the previous AY.

Both use `func.count(func.distinct(func.date(LabSession.checked_in_at)))` for the day-counting. Cheap query; runs in <10 ms on a decade of data.

#### `isel/services/stats.py`

Heavier read-side aggregations powering the dashboard.

- **`daily_log(date_str=None) → list[dict]`** — All IN/OUT events for one calendar day, newest first.
- **`monthly_user_stats(year, month) → list[dict]`** — Per-user `sessions` + `total_minutes` for the month.
- **`weekly_checkin_counts() → list[dict]`** — 7-day trend of unique check-ins (one bar per day).
- **`today_unique_checkins() → int`**, **`active_days_this_month() → int`** — Overview stat cards.
- **`get_user_profile(user_id) → dict`** — Powers the profile modal: month-to-date stats + 10 recent sessions.
- **`export_monthly_csv(year, month) → list[dict]`** — Rows for the CSV download.
- **`weekly_grid(start_date, user_ids) → list[dict]`** — The GitHub-style attendance grid (rows = members, cols = 7 days). Each cell carries `total_minutes`, `sessions`, `has_anomaly`. **Anomaly heuristic:** session >12 h, or method == `auto_checkout`.
- **`anomalies(days=7) → list[dict]`** — Per-user counters (missing weekdays, long sessions).

#### `isel/services/audit.py`

Two functions only:

- **`record(action_type, target_user_id, target_name, performed_by='admin')`** — Write one row. Most services call this directly after their main commit.
- **`recent_entries(limit=200, user_id=None, user_ids=None, action_types=None, start=None, end=None, q=None) → list[dict]`** — The query interface. Powers the Activity Log tab + CSV export. All filters are optional and AND-ed together. `q` is a case-insensitive `LIKE` against `target_name` OR `action_type`.

### 4.5 API blueprints

[isel/api/__init__.py](isel/api/__init__.py) registers seven blueprints in `register_blueprints(app)`:

```python
from isel.api import auth, checkin, users, sessions, presence, stats, admin
for mod in (auth, checkin, users, sessions, presence, stats, admin):
    app.register_blueprint(mod.bp)
```

#### Complete endpoint reference

| Method | Path | Auth | Blueprint | Behavior |
|---|---|---|---|---|
| POST | `/api/admin/login` | — | auth | PIN check with HMAC compare + 5-fails-per-IP / 60-s lockout |
| POST | `/api/admin/logout` | admin | auth | Clear session |
| GET | `/api/admin/status` | — | auth | `{authenticated: bool}` |
| POST | `/api/auth` | — | checkin | Match a face. Returns `{matched, user_id, name, status, low_confidence}`. Stashes 30-s `pending_toggle` token in session. |
| POST | `/api/toggle` | — | checkin | Flip presence. Validates the `pending_toggle` token (skipped for `check_in_method='manual'`). Triggers Slack update. |
| POST | `/api/register` | admin | users | Create new user with up to 3 variants. Rejects duplicates by face. |
| GET | `/api/users` | — | users | All users with `{id, name, type, status, has_face, face_variants, last_seen}` |
| GET | `/api/user/<id>/profile` | — | users | Profile + monthly stats + 10 recent sessions |
| PUT | `/api/user/<id>` | admin | users | Update name + user_type |
| DELETE | `/api/user/<id>` | admin | users | Delete user (sessions kept; audit log preserved via `target_name` snapshot) |
| POST | `/api/user/<id>/face` | admin | users | Replace one variant slot `{variant, images: [b64, ...]}` |
| PUT | `/api/session/<id>` | admin | sessions | Edit session timestamps |
| GET | `/api/present` | — | presence | List of present names |
| GET | `/api/present-detailed` | — | presence | List with id/type/duration |
| GET | `/api/log/today` | — | stats | Today's IN/OUT events |
| GET | `/api/log?date=YYYY-MM-DD` | — | stats | Events for a specific date |
| GET | `/api/stats/today` | — | stats | `{unique_checkins, active_days_month}` |
| GET | `/api/stats/weekly` | — | stats | 7-day check-in trend |
| GET | `/api/stats/weekly-grid?start=&user_ids=` | — | stats | Per-user × per-day attendance grid |
| GET | `/api/stats/monthly?year=&month=` | — | stats | Per-user sessions + minutes for the month |
| GET | `/api/stats/anomalies?days=N` | — | stats | Anomaly counters |
| GET | `/api/export/csv?year=&month=` | admin | stats | Download month's sessions as CSV |
| GET | `/api/stats/points?year=&month=` | — | admin | Monthly leaderboard |
| GET | `/api/stats/points/year?year=` | — | admin | Academic-year leaderboard `{year, leaderboard}` |
| GET | `/api/audit/log` | admin | admin | Filtered audit log |
| GET | `/api/audit/export.csv` | admin | admin | Audit log as CSV (10 k row cap) |
| POST | `/api/admin/promote-students` | admin | admin | Apply explicit promotion batch |

#### Common patterns

- **Auth gate.** Admin routes use the `@admin_required` decorator from [isel/utils/__init__.py](isel/utils/__init__.py) — returns 403 if `session.get('admin')` is falsy.
- **Error shape.** Services return `{'success': False, 'message': '...'}` on validation failure; routes pass that through with the right HTTP status (usually 400 or 500).
- **Global error handler.** `ImageDecodeError` raised by [isel/utils/image.py](isel/utils/image.py) is caught in `app.py` and turned into a 400 JSON response — so route code doesn't have to wrap every `decode_image()` call.
- **Image size limits.** `MAX_CONTENT_LENGTH = 8 MB` at the Flask layer (rejected at request parse time), plus `_MAX_IMAGE_BYTES = 5 MB` per image in `decode_image()`.
- **Session-stashed pending toggle.** `/api/auth` puts `{user_id, expires}` in the Flask session under `pending_toggle`. `/api/toggle` requires it match (for face flow) before flipping state — prevents a malicious client from POSTing a toggle for someone else's user_id.

---

## 5. Face Recognition Pipeline

This is the part new developers are most nervous about. It's actually simpler than it looks because **all the ML lives in one file** ([isel/face_engine.py](isel/face_engine.py), 54 lines).

### 5.1 Why ArcFace

DeepFace is a Python wrapper around several face-recognition models. We use **ArcFace** because:

1. It returns a 512-dim embedding (lots of discrimination capacity).
2. Cosine distance between two embeddings of the same person is reliably < 0.5 under our lighting.
3. It's fast: ~200 ms per frame on CPU.

We don't fine-tune. Out-of-the-box pretrained weights work well enough for a roster of ~15 people.

### 5.2 The 3-variant slot system

Each user can store embeddings under three named slots:

| Slot | Captured with | Optional? |
|---|---|---|
| `normal` | Plain face, no glasses, no mask | **No** — required for registration |
| `glasses` | Wearing glasses | Yes |
| `mask` | Wearing a mask | Yes |

Each slot holds up to 3 embeddings (burst capture — 3 frames in ~1 second). Total cap: **9 embeddings per user.**

#### Storage shape on `User.embedding` (JSON column)

```json
{
  "normal":  [[0.012, -0.443, ...], [0.014, -0.441, ...], [0.011, -0.440, ...]],
  "glasses": [[0.021, -0.330, ...]],
  "mask":    []
}
```

#### Backward compatibility — `_as_variant_dict()`

Older rows have different shapes. The normalizer handles all of them:

| Input shape | Output |
|---|---|
| `None` or `[]` or `{}` | `{}` |
| `[0.012, -0.443, ...]` (flat list of floats — legacy single vector) | `{'normal': [<that list>]}` |
| `[[0.01, ...], [0.02, ...]]` (legacy list of vectors) | `{'normal': [first 3 vectors]}` |
| `{'normal': [...], 'glasses': [...]}` (current) | Filtered to valid keys, capped at 3 frames each |

**Always read embeddings through `_as_variant_dict`**. Never index `user.embedding['normal']` directly — you'll crash on a legacy row.

### 5.3 The matching algorithm

`FaceEngine.find_match(probe_vec, threshold)` in [isel/face_engine.py:24-53](isel/face_engine.py#L24-L53):

```
1. For every user (via get_all_embeddings()):
     For every variant of that user:
       For every stored vector in that variant:
         dist = cosine(probe_vec, stored_vec)
         if dist < min_so_far:
           min_so_far = dist
           best_user_id = user_id
2. Return (best_user_id, best_name, min_so_far) — or (None, None, None) if no candidate beat the threshold.
```

It's a brute-force scan. With 15 users × 9 variants × ~200 ns per cosine = **<30 μs total per match**. We don't need an ANN index until we have thousands of faces.

**Extending the algorithm:** if you want to add per-variant averaging or use a different distance metric, change it inside `find_match` only. Callers (just `isel/api/checkin.py` and `isel/api/users.py`) treat it as an opaque oracle that returns `(user_id, name, distance)`.

### 5.4 Thresholds

| Constant | Value | Where set | What it gates |
|---|---|---|---|
| `auth_threshold` | 0.55 | `FaceEngine.__init__` | Whether a check-in face counts as a match (cosine distance must be below this) |
| `reg_threshold` | 0.50 | `FaceEngine.__init__` | Whether a new registration is rejected as a duplicate of an existing user (stricter — we want to be sure before refusing to register) |
| `LOW_CONFIDENCE_THRESHOLD` | 0.40 | env var (`.env`) | UI's "low confidence" badge — shown when match distance is between this and `auth_threshold` |

**Important distinction:** `LOW_CONFIDENCE_THRESHOLD` is purely cosmetic — it controls the badge in the UI. The actual match decision uses `auth_threshold` (0.55). Changing the env var does **not** change which faces are accepted.

If you change the camera or move it to a different lighting environment, re-tune these:

1. Register a few people.
2. Add a few `print(dist)` calls in `find_match`.
3. Watch values in the console as you check in / out across a day.
4. Pick a threshold ~0.05 above the worst legitimate match.
5. Remove the `print` calls. Update this guide's table with the new value + rationale.

### 5.5 Registration flow — the 3-step wizard

```
Admin opens "Add Member" modal
         │
         ▼
    Enter name + role
         │
         ▼
┌─ Step 1 ─ Normal (required) ──┐
│ Camera live, "Capture" button │
│ → captureBurst(3 frames)      │
└──────────┬────────────────────┘
           ▼
┌─ Step 2 ─ Glasses (skippable) ┐
│ "Capture" or "Skip"           │
└──────────┬────────────────────┘
           ▼
┌─ Step 3 ─ Mask (skippable) ───┐
│ "Capture" or "Skip"           │
└──────────┬────────────────────┘
           ▼
   Submit all captured variants
   → POST /api/register {variants: {normal: [...], glasses: [...], mask: [...]}}
```

Frontend lives in [ui/js/dashboard/modals.js](ui/js/dashboard/modals.js):

- `REG_STEPS` — the wizard config (label, key, required flag per step)
- `_renderRegStep()` — draws the current step into the modal
- `onRegStepCapture()` / `onRegStepSkip()` — step navigation
- `_submitRegistration()` — packages all collected base64 frames and POSTs
- `captureBurst(videoId, count=3, gapMs=350)` — snaps N frames spaced N ms apart

**Per-slot retake** for existing users uses the same modal but targets one slot only (`/api/user/<id>/face` with `{variant, images}`).

---

## 6. Frontend Architecture

### 6.1 Conventions

- **All JS files are IIFE-wrapped** (`(function () { ... })();`). This keeps module-private variables off `window`.
- **Public functions are exposed via `window.foo = function foo() { ... }`** so inline HTML `onclick=` handlers can find them. Yes, we use inline handlers — they're easy to read, you can `Cmd+F` them, and we have no build step to add an event-listener layer.
- **No build step, no bundler.** Files load in fixed order from `<script>` tags at the bottom of [ui/index.html](ui/index.html). Tree-shaking is "delete unused code yourself."
- **Vanilla JS only.** No React, no Vue, no jQuery. Reason: this codebase needs to survive 10+ years of student turnover. Every framework we picked in 2025 will be deprecated by 2030; the DOM API will not be.
- **One file = one concern.** When a JS file passes ~300 lines, split it.

### 6.2 File map

| File | Purpose |
|---|---|
| [ui/index.html](ui/index.html) | Single-page shell — top nav, check-in markup, dashboard markup (4 tabs), all modals. ~485 lines. Both screens swap via `.screen.active`. |
| [ui/css/tokens.css](ui/css/tokens.css) | CSS variables only (colors, spacing). Re-skin the app by editing this file. |
| [ui/css/base.css](ui/css/base.css) | Reset, topbar, modals, shared buttons. |
| [ui/css/checkin.css](ui/css/checkin.css) | Kiosk screen styles. |
| [ui/css/dashboard.css](ui/css/dashboard.css) | Dashboard styles. Largest file (~900 lines). |
| [ui/js/core/api.js](ui/js/core/api.js) | Tiny fetch wrapper — `api.get(url)`, `api.post(url, body)`. |
| [ui/js/core/camera.js](ui/js/core/camera.js) | `startCamera(videoId)` / `stopCamera()` / `captureFrame(video) → base64`. |
| [ui/js/core/clock.js](ui/js/core/clock.js) | Top-bar clock. |
| [ui/js/core/nav.js](ui/js/core/nav.js) | `switchScreen()` + global `C`/`D` keyboard shortcuts. Modal-open guard. |
| [ui/js/core/cohort-multiselect.js](ui/js/core/cohort-multiselect.js) | Multi-select with preset buttons (All / 先生 / M2 / M1 / B4 / Intern / 学生). Smart popover positioning (flips when overflowing viewport). |
| [ui/js/core/utils.js](ui/js/core/utils.js) | `initials()`, `avColor()`, formatters. |
| [ui/js/checkin/index.js](ui/js/checkin/index.js) | Bootstraps the kiosk screen + keyboard handlers. |
| [ui/js/checkin/state-machine.js](ui/js/checkin/state-machine.js) | `idle` / `scanning` / `confirmation` / `fail` / `success` rendering. |
| [ui/js/checkin/manual-picker.js](ui/js/checkin/manual-picker.js) | Modal for picking a member manually when face match fails. |
| [ui/js/checkin/presence-strip.js](ui/js/checkin/presence-strip.js) | Bottom strip showing present (green) + absent (grey) members. |
| [ui/js/dashboard/index.js](ui/js/dashboard/index.js) | Tab dispatcher (`switchDashTab`) + 30 s polling + `1`/`2`/`3`/`4` shortcuts. |
| [ui/js/dashboard/overview.js](ui/js/dashboard/overview.js) | Stat cards + 7-day trend chart + activity log section. |
| [ui/js/dashboard/attendance.js](ui/js/dashboard/attendance.js) | Monthly + academic-year leaderboards. |
| [ui/js/dashboard/attendance-grid.js](ui/js/dashboard/attendance-grid.js) | Weekly GitHub-style grid. |
| [ui/js/dashboard/activity.js](ui/js/dashboard/activity.js) | Audit log with filters + CSV export. |
| [ui/js/dashboard/members.js](ui/js/dashboard/members.js) | Member list + edit/delete/promote actions. |
| [ui/js/dashboard/modals.js](ui/js/dashboard/modals.js) | Registration wizard, profile modal, promote wizard, PIN modal, face-rereg modal, context modal. ~400 lines. |

### 6.3 Check-in screen state machine

States cycle in this order:

```
   ┌──────────┐    Enter    ┌──────────┐  matched   ┌─────────────┐  Enter   ┌─────────┐
   │   idle   │ ──────────► │ scanning │ ─────────► │ confirmation│ ───────► │ success │
   └──────────┘             └──────────┘            └─────────────┘          └────┬────┘
        ▲                         │ unmatched              │ Esc                  │ 3 s
        │                         ▼                        │                      │
        │                    ┌──────────┐                  └──────────────────────┤
        │   Esc / 3 s        │   fail   │                                         │
        └────────────────────┴──────────┘ ◄───────────────────────────────────────┘
                                                                       (back to idle)
```

Defined in [ui/js/checkin/state-machine.js](ui/js/checkin/state-machine.js). Each state has a config object (`tagClass`, `tagText`, `name`, `sub`, `faceClass`, `scanLine`, `card`, `btnText`, `btnDisabled`, `hints`) and `setState(key)` applies all of them in one call.

**Adding a new state:** add an entry to `CHECKIN_STATES`, then transition into it from wherever makes sense (`setState('mynewstate')`). If the state needs dynamic content (like `confirmation`), write a dedicated `setStateXxx()` function.

**Keyboard bindings** (defined in [ui/js/checkin/index.js](ui/js/checkin/index.js)):

| Key | When state = | Action |
|---|---|---|
| `Enter` | `idle` | Scan |
| `Enter` | `confirmation` | Confirm toggle |
| `Enter` | `fail` / `success` | Reset to idle |
| `Space` | `idle` / `fail` | Open manual picker |
| `Esc` | `confirmation` / `fail` | Back to idle |
| `C` (global) | any | Switch to check-in screen |
| `D` (global) | any | Switch to dashboard |

The global `C` / `D` handlers in [ui/js/core/nav.js](ui/js/core/nav.js) check whether any modal is open and bail if so — otherwise `D` would switch screens out from under an open Add Member modal.

### 6.4 Dashboard tabs

Four tabs: `overview` (1), `attendance` (2), `members` (3), `activity` (4). Defined by `<div class="db-page" id="db-<name>">` blocks in [ui/index.html](ui/index.html) — only one has class `active` at a time.

`switchDashTab(name, btn)` in [ui/js/dashboard/index.js](ui/js/dashboard/index.js) handles the swap. For `members` and `activity`, it first calls `checkAdminAndProceed(...)` which gates behind PIN entry if not already authenticated.

`loadDashboard()` is called on initial screen-switch and then re-run every 30 s by `setInterval`. It calls `loadOverview()`, `loadLogSection()`, and `loadMembers()` in parallel. Tab-specific data (attendance leaderboards, activity log) loads only when that tab is switched to.

**There is no formal `init`/`destroy` lifecycle per tab** — the simpler dispatcher above has been sufficient. If a future tab needs cleanup (e.g. a websocket), introduce that lifecycle then. Don't add it preemptively.

### 6.5 Modals

All modals are direct children of `<body>`, hidden by default with class `hidden`, shown by removing that class. IDs: `reg-modal` / `pin-modal` / `profile-modal` / `face-rereg-modal` / `context-modal` / `promote-modal` / `picker-modal`. Keyboard handlers consult this list to know when to suppress global shortcuts.

---

## 7. Configuration & Environments

[config.py](config.py) defines four classes:

| Class | When | Notes |
|---|---|---|
| `Config` | base | Loads all env vars with safe defaults |
| `DevConfig` | `create_app('dev')` (default) | `DEBUG=True`, cookies not secure |
| `ProdConfig` | `create_app('prod')` (via `wsgi.py`) | `DEBUG=False`, cookies secure. **Raises `RuntimeError` if `FLASK_SECRET_KEY` or `ADMIN_PIN` is missing.** |
| `TestConfig` | `create_app('test')` (tests) | In-memory SQLite, fixed test PIN/secret |

### Environment variables

| Name | Default | Required? | What it does |
|---|---|---|---|
| `FLASK_SECRET_KEY` | `dev-secret-change-me` | **Yes in prod** | Flask session signing key. Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `ADMIN_PIN` | (empty) | **Yes** | PIN for admin dashboard. Any length string. Stored plaintext — this is fine for an on-premise lab kiosk. |
| `DATABASE_URL` | `sqlite:///isel_room.db` | No | SQLAlchemy connection string. Use MySQL URL in production at scale. |
| `LOW_CONFIDENCE_THRESHOLD` | `0.40` | No | UI badge threshold (see [5.4](#54-thresholds)). **Does not affect match decisions.** |
| `DAY_RESET_HOUR` | `22` | No | Currently informational only — the cron job runs whenever you schedule it, this is just documentation of "when the lab logically closes." |
| `SLACK_BOT_TOKEN` | (empty) | No | Set to enable Slack status board. Omit to disable cleanly. |

`.env` is loaded by `python-dotenv` at the top of [app.py](app.py). Copy `.env.example` to `.env` and fill in.

---

## 8. Slack Integration

**Important:** we deliberately do **not** have a Slack chat listener. There is no Socket Mode, no message handlers, no `SLACK_APP_TOKEN`. Just one HTTP-only bot token that posts and edits one message per day.

### What it does

- Maintains a single "status board" message in `#a-lab-status`, refreshed in place via `chat.update` whenever presence changes.
- Plain text format (no Block Kit):

```
🟢 *3 in the lab*
• Inoue (M2)
• Naimi (M1)
• Yamamoto (B4)

_Updated 14:32_
```

When empty:
```
⚫ *Lab is empty*

_Updated 14:32_
```

### How it works

[isel/integrations/slack.py](isel/integrations/slack.py) — the whole file is ~80 lines.

- `slack_state.json` (at repo root, gitignored) caches `{ts, date, channel}` — the timestamp of today's message so we can edit it.
- On each call to `update_status_board()`:
  1. Render the new text from `get_present_users_detailed()`.
  2. If `state['date'] == today`, call `chat.update(channel, ts, text)`.
  3. If that returns `message_not_found` (someone deleted it), fall through to step 4.
  4. Otherwise — new day, or no state — `chat.postMessage(channel, text)` and save the returned `ts` to `slack_state.json`.
- Any error is caught and logged. **Failures never block check-ins.**

### Who calls it

- [isel/api/checkin.py](isel/api/checkin.py) — after every successful `/api/toggle`.
- [isel/services/attendance.py](isel/services/attendance.py) — at the end of `auto_checkout_all()`.

### Setup

1. Create a Slack app at api.slack.com/apps.
2. Add bot scopes: `chat:write`.
3. Install to your workspace, copy the bot token (`xoxb-...`).
4. Invite the bot to `#a-lab-status` (`/invite @YourBot`).
5. Put the token in `.env` as `SLACK_BOT_TOKEN`.
6. Restart the app — you should see `Slack: Bot Client Initialized` in the console.

To use a different channel, change `_DEFAULT_CHANNEL` in [isel/integrations/slack.py](isel/integrations/slack.py) (or pass `channel=` to `update_status_board()` from the caller).

---

## 9. Background Jobs

### Auto-checkout

One CLI command: `flask auto-checkout`. Closes all open sessions, marks every user OUT, writes `AUTO_CHECKOUT` audit rows, refreshes Slack. Idempotent — safe to run twice.

Schedule it nightly via cron at your lab's closing time (e.g. 22:00):

```cron
# crontab -e
0 22 * * *  cd /path/to/isel_room && FLASK_APP="app:create_app" flask auto-checkout
```

**Why a CLI command instead of a daemon thread?** A previous version ran auto-checkout from a daemon thread inside the Flask app. Problems: hard to debug when it failed, doubled in dev because of Werkzeug's reloader, no record of whether it actually ran. Cron is older than Python, every sysadmin understands it, logs are in syslog. Boring is good for infrastructure.

If you miss a cron tick, no big deal — `_close_stale_session` in `attendance.py` closes any session open >24 h the next time that user checks in.

---

## 10. Testing

### Stack

- `pytest`
- `pytest-flask`
- **In-memory SQLite per test** (via `StaticPool` in [tests/conftest.py](tests/conftest.py)) — tests are fast and isolated.

### Fixtures

| Fixture | Scope | What it gives you |
|---|---|---|
| `app` | session | A `create_app('test')` instance |
| `client` | function | `app.test_client()` for HTTP calls |
| `admin_client` | function | `client` already logged in with the test PIN |
| `db_session` | function | A direct SQLAlchemy session for test setup |
| `_clean_db` | autouse | Truncates all tables after each test |

### How tests look

The standard pattern:

```python
def test_something(db_session):
    user = _make_user(db_session, name='Alice', user_type='M1')
    # ... set up rows ...
    db_session.commit()

    result = service_under_test.do_thing(user.user_id)

    assert result['expected_field'] == expected_value
```

For API tests:

```python
def test_api_thing(admin_client):
    resp = admin_client.post('/api/admin/promote-students',
                              json={'promotions': [{'user_id': 1, 'new_type': 'M2'}]})
    assert resp.status_code == 200
    assert resp.json['success'] is True
```

### Date-pinning gotcha

Tests that exercise date-window logic must pin dates explicitly — not use `date.today()`. Otherwise the test passes 11 months a year and breaks every April. See [tests/test_points.py](tests/test_points.py) for the pattern: derive `ay = points.current_academic_year()` then build datetimes like `datetime(ay, 4, 10, ...)`.

### Run the suite

```bash
python -m pytest                  # all tests, quiet
python -m pytest -v               # verbose
python -m pytest tests/test_points.py::test_academic_year_boundary  # one test
python -m pytest -k "promote"     # tests matching keyword
```

---

## 11. Common Workflows (Recipes)

### 11.1 Add a new API endpoint

**Goal:** "I want `GET /api/users/<id>/sessions` to return a user's last 50 sessions."

1. **Pick a blueprint.** Sessions live in `isel/api/sessions.py`, but this endpoint is keyed by user — put it in `isel/api/users.py`.
2. **Add a service function.** In `isel/services/stats.py` (or whichever fits), write:
   ```python
   def get_user_sessions(user_id: int, limit: int = 50) -> list[dict]: ...
   ```
3. **Wire the route.**
   ```python
   # isel/api/users.py
   @bp.get('/api/user/<int:user_id>/sessions')
   def get_user_sessions(user_id: int):
       from isel.services.stats import get_user_sessions as svc
       return jsonify(svc(user_id))
   ```
4. **Add a test.** Copy the closest existing test in `tests/test_users.py`, adapt.
5. **Update this guide's endpoint table** in [section 4.5](#45-api-blueprints).

### 11.2 Add a new dashboard tab

**Goal:** "I want a `Reports` tab in the sidebar."

1. **Add markup** in [ui/index.html](ui/index.html):
   - Sidebar button next to the existing ones (copy one and edit). Set `id="sbt-reports"`.
   - Page block: `<div class="db-page" id="db-reports">...</div>`.
2. **Create JS file** `ui/js/dashboard/reports.js`:
   ```js
   (function () {
     window.loadReports = async function loadReports() {
       const data = await api.get('/api/whatever');
       document.getElementById('reports-content').innerHTML = render(data);
     };
   })();
   ```
3. **Add `<script>` tag** at the bottom of [ui/index.html](ui/index.html).
4. **Wire the tab dispatcher** in [ui/js/dashboard/index.js](ui/js/dashboard/index.js):
   - Add to `PAGE_META`: `reports: { title: 'Reports', subtitle: '...' }`.
   - Add to `tabMap`: `'5': { name: 'reports', btnId: 'sbt-reports' }`.
   - Add a branch in `switchDashTab` to call `loadReports()`.
5. **Gate behind admin if needed.** Add `name === 'reports'` to the `checkAdminAndProceed` condition.

### 11.3 Change face matching threshold

1. Edit defaults in `FaceEngine.__init__` in [isel/face_engine.py](isel/face_engine.py).
2. Run `python -m pytest tests/test_face_engine.py` — adjust any threshold-sensitive assertions.
3. Update [section 5.4](#54-thresholds) of this guide with the new value + a one-line rationale (e.g. "raised to 0.58 after camera replacement").
4. Commit: `fix(face): bump auth_threshold to 0.58 after camera swap`.

### 11.4 Add a new member role

**User types are free-text strings** in `User.user_type`. No enum, no validation.

To add e.g. `Postdoc`:

1. **No code change needed in models.** Just start using the new value.
2. **Update the promotion wizard** in [ui/js/dashboard/modals.js](ui/js/dashboard/modals.js) — add `Postdoc` to the available target types in the wizard step where the admin picks the new role.
3. **Update seed data** in [seed_db.py](seed_db.py) if you want a sample Postdoc to appear in mock data.
4. **Update the cohort filter buttons** in [ui/js/core/cohort-multiselect.js](ui/js/core/cohort-multiselect.js) if you want a one-click "Postdoc" preset.
5. **Update the glossary** in section 1 of this guide.

### 11.5 Debug a face match failure

Symptoms: User stands in front of camera; `/api/auth` returns `{matched: false}`.

1. **Check whether the user has any face data.** Members tab → look at the row → if the face indicator is off, they need to register.
2. **Try re-registration.** Members tab → that row → Re-Register Face → capture all 3 variants in good lighting.
3. **Check if `LOW_CONFIDENCE_THRESHOLD` is involved.** If `matched: true` but `low_confidence: true`, the UI is showing the "low confidence" badge — match still works. If matches are flickering, raise the env var.
4. **Add temporary logging** to `find_match`:
   ```python
   print(f'probe vs {info["name"]} ({_variant_key}): {dist:.3f}')
   ```
   Restart the app, do a few check-ins, watch the console. You'll see exactly which stored variants are close and which are far. Remove the print before committing.

### 11.6 Reset the database

```bash
python seed_db.py
```

Wipes everything, creates 11 mock members, ~60 days of session history, ~3 currently-in-lab. Always safe.

If you want a clean DB with no mock data, delete `isel_room.db` and let `init_db()` recreate empty tables on next app start.

---

## 12. Conventions & House Style

### Commits

We use [Conventional Commits](https://www.conventionalcommits.org/). Format:

```
<type>(<scope>): <subject>

<optional body explaining the why>
```

Types we use: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`. Examples from this repo's history:

```
feat(points): academic-year leaderboard resets every Apr 1
fix(ui): rotate avatar colours in kiosk manual picker
refactor(ui): switch structural surfaces to warm-cream neutral palette
chore(seed): update members to actual lab roster
```

**Subject in lowercase, no trailing period.** Past tense or imperative — pick one and stick with it (this repo leans imperative).

### Attribution

**Never include `Co-Authored-By` lines.** Never credit AI assistants in commit messages or PR descriptions. The work is yours. If you used Claude / Copilot / etc. to write code, that's a tool, like an IDE.

In the Claude Code config (`.claude/settings.json` or equivalent), the attribution setting should be:
```json
"attribution": { "commit": "", "pr": "" }
```

### Code style

- **Default to no comments.** Code should be self-documenting through good naming. Add a comment only when the *why* is non-obvious: a hidden constraint (`# tokens must be HMAC-compared to prevent timing attacks`), a workaround (`# DeepFace 0.0.79 leaks file handles when enforce=True`), or surprising behavior. Don't comment what the code does — it's right there.
- **No dead code.** Don't leave `# old code commented out` blocks. `git log` is the archive. If you need to remove something, delete it; if you need it back, `git checkout`.
- **No premature abstractions.** Three similar lines of code are better than a forced helper function. Wait until you have 3 *real* call sites before extracting.
- **No backwards-compat shims for code you control.** If you rename a function, update every caller — don't leave a wrapper that calls the new name.
- **Trust internal code.** Validate at system boundaries (user input, external APIs). Don't `if user is None: ...` after a `session.get(User, user_id)` if the caller has already guaranteed the user exists.

### Naming

- Python: `snake_case` functions, `PascalCase` classes, `UPPER_SNAKE` constants.
- JS: `camelCase` functions and variables; functions exposed to inline handlers via `window.foo = function foo() {...}` (named both for stack traces).
- CSS: `kebab-case` class names.
- Files: `snake_case.py`, `kebab-case.js`, `kebab-case.css`.

### Japanese in the UI

Japanese terms (`先生`, `学生`, `年度`) are intentional in UI strings, audit rows, and Slack messages. The codebase itself (variable names, function names, identifiers) is all English. This split is deliberate: ASCII identifiers keep tooling happy, Japanese labels keep the UI feeling native to its users.

### File length

When a file passes ~400 lines, consider whether it's doing two things. `ui/js/dashboard/modals.js` is at ~400 and on the edge — if you add another modal, split.

---

## 13. Known Limitations & Future Work

| Limitation | Workaround | Future fix |
|---|---|---|
| SQLite single-writer | Fine for 1 lab × ~15 users × decade of sessions | Switch to MySQL via `DATABASE_URL` if scale grows |
| DeepFace + TensorFlow loads ~500 MB at startup (~10 s cold start) | Keep the app process running; use `wsgi.py` + gunicorn in prod | Could swap to insightface (smaller) but ArcFace via DeepFace is well-tested for us |
| No multi-tenant support | Run one app instance per lab | Add `lab_id` column on every table — non-trivial |
| `ADMIN_PIN` is plaintext in `.env` | Acceptable for kiosk on a trusted network | Hash + per-user admin accounts |
| One Slack channel only | Edit `_DEFAULT_CHANNEL` per deployment | Per-channel config |
| No password rotation alerting | Manual `.env` update | Maybe a CLI `flask rotate-pin` |
| Mobile dashboard unstyled | Use a tablet or laptop | Responsive CSS rewrite (~2 days work) |
| No CSV import for bulk member registration | Use `seed_db.py` template + edit | Build it if it's ever asked for |
| No browser compatibility tested below Chrome/Firefox/Safari current | — | Polyfill / test if needed |

### Candidate next features (from sensei wish list)

- 2FA for admin login (TOTP).
- Photo capture along with each check-in (separate `images/checkins/` directory, served back in admin view) — privacy implications need discussion.
- Discord integration alongside Slack.
- Mobile-friendly read-only dashboard.

---

## 14. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| App won't start: `RuntimeError: FLASK_SECRET_KEY must be set...` | Running `create_app('prod')` without env vars | Set `FLASK_SECRET_KEY` and `ADMIN_PIN` in `.env`, or use `create_app('dev')` for local |
| App won't start: `ModuleNotFoundError` | Not in venv, or missing dep | `source .venv/bin/activate && pip install -r requirements.txt` |
| Browser console: `switchScreen: missing element for "..."` | Old cached HTML after a Jinja change | Hard refresh (Cmd+Shift+R). If still broken, restart Flask — `TEMPLATES_AUTO_RELOAD=True` is set but Werkzeug sometimes misses changes to `<script>` tag ordering |
| Face never matches anyone | Lighting, glasses, mask, or stale embeddings | Re-register with all 3 variants in current lighting |
| Face match flicker (matched / not / matched / not) | Distance is right at the threshold | Raise `auth_threshold` slightly or recapture |
| Slack message duplicated | `slack_state.json` got out of sync | Delete `slack_state.json` — next call will post fresh |
| Slack errors silently failing | Console shows `Slack: SLACK_BOT_TOKEN is missing` or `Slack status board update failed: ...` | Check `.env`, check bot is in the channel |
| Tests fail in early April | A test used `date.today()` instead of pinning dates | Find the offender; refactor to `points.current_academic_year()` |
| `/api/toggle` returns "No active auth session" | More than 30 s elapsed between `/api/auth` and `/api/toggle` | Scan again; the pending_toggle token expired |
| Admin login locked out | Too many wrong PIN attempts (5 per IP, resets after 60 s) | Wait 60 s |
| Dev DB out of sync after schema change | No migrations — drop tables manually | `python seed_db.py` (or delete `isel_room.db` for empty) |
| Camera permission denied in browser | First-time prompt missed | Click lock icon → site settings → allow camera; or chrome://settings/content/camera |
| Auto-checkout doesn't run | Cron not configured, or wrong path in crontab | `crontab -l` to verify; check syslog for cron errors |

---

## 15. Getting Help

When you're stuck:

1. **Re-read the relevant section here.** Often the answer is in the gotcha you skimmed.
2. **`git log -p <file>`** — the commit history explains *why* things are the way they are. Reading recent commits in the area you're modifying is the single best way to absorb context.
3. **Run the tests.** They encode invariants. If you're not sure whether a refactor is safe, `pytest`.
4. **Original team:** _(placeholder — fill in names + contact when handing over)_.
5. **GitHub issues:** _(placeholder — link to the repo's issues tab)_.

### Conventional commits cheat sheet

```
feat:     New feature visible to users
fix:      Bug fix
refactor: Code change that neither fixes a bug nor adds a feature
chore:    Build/tooling/config (no production code)
docs:     Documentation only
test:     Tests only
perf:     Performance improvement
style:    Formatting (no code change)
```

Subject in lowercase, no period, ≤ 70 chars. Optional body wrapped at 72.

---

_This guide is part of the codebase. If you change something architectural, update the relevant section in the same commit — `feat(x): do the thing` and `docs(guide): document the thing` together. Future you will thank present you._
