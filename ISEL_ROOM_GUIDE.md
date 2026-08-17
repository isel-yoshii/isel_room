# Developer Guide for ISEL 在室管理システム

> **For the next generation of maintainers.** This guide is the single source of truth for how the system is built, how to extend it, and the pitfalls you would otherwise learn the hard way. Read it once cover to cover on your first day, then keep it open as a reference.

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

You are a junior developer (B4 / M1 / Intern) who has just been handed this codebase to maintain and extend. You may be the only person actively working on it for months at a time. This guide assumes you know what programming is, but does **not** assume you have used Flask, SQLAlchemy, or DeepFace before.

### How to use this guide

- **First read (1 to 2 hours).** Read sections 1 to 6 top to bottom. Skip code blocks on the first pass and focus on the prose.
- **Second pass.** Read with the codebase open. For each file mentioned, open it and read the first 20 lines.
- **Day to day.** Treat sections 7 to 14 as a reference. Section 11 (recipes) is the most used.
- **Before changing anything.** Read section 12 (conventions). Diverging from house style is the fastest way to make this codebase hard to maintain.

### Prerequisites (and where to learn each)

| You should know | Where to learn (free) |
|---|---|
| Python 3 basics | [docs.python.org/3/tutorial](https://docs.python.org/3/tutorial/) |
| Flask (web framework) | [flask.palletsprojects.com/en/3.0.x/quickstart](https://flask.palletsprojects.com/en/3.0.x/quickstart/) |
| SQLAlchemy 2.0 (ORM) | [docs.sqlalchemy.org/en/20/tutorial](https://docs.sqlalchemy.org/en/20/tutorial/index.html) |
| Modern JavaScript (ES2020+) | [javascript.info](https://javascript.info/) |
| Git + conventional commits | [conventionalcommits.org](https://www.conventionalcommits.org/) |

You do **not** need to learn DeepFace internals. We wrap it in one file and you will rarely touch it.

### Glossary

| Term | Meaning |
|---|---|
| `先生` (sensei) | Faculty or professor. The lab head. |
| `学生` (gakusei) | Student. Covers B4, M1, M2, PhD, Intern. |
| `B4` | 4th-year undergraduate (final year before grad school) |
| `M1` / `M2` | 1st / 2nd year master's student |
| `PhD` | Doctoral student |
| `Intern` | Short-term researcher (not on the formal promotion path) |
| `卒業` (sotsugyō) | Graduated. Terminal state, no longer active. |
| `AY` / `年度` | Academic year (Apr 1 to Mar 31, Japanese system) |
| **Embedding** | A fixed-length vector summarising a face. We use 512 floats from ArcFace. |
| **Cosine distance** | A number in [0, 2] measuring how different two vectors are. 0 means identical, 2 means opposite. We treat anything below 0.55 as "same person." |
| **Variant slot** | One of `normal` / `glasses` / `mask`. Each user can store up to 3 frames per slot (max 9 embeddings per user). |
| **Burst capture** | Snapping 3 frames in quick succession (~350 ms apart) to capture micro-pose variation. |

---

## 2. System Overview

### The problem

The ISEL lab wants to know, at any moment, **who is in the room**. They also want history (who comes in often? when?) and a paper trail (who let themselves in late on Sunday?).

We built a face-recognition turnstile. A tablet or laptop at the door runs a web page that watches the camera. When someone walks up, their face is matched against the member roster and a check-in event is recorded.

### What it is not

- Not a security gate. Anyone can walk past the camera. The system is for **tracking**, not enforcement.
- Not a time-clock for billable hours. Points equal days present, not minutes worked.
- Not multi-lab. One install equals one lab.

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
| Dashboard | `/` then press `D` | Sensei and admins | `1`/`2`/`3`/`4` tabs · PIN gates admin tabs |

Both live in the same single-page app (`ui/index.html`). They are toggled via `switchScreen('check-in' | 'dashboard')` in [ui/js/core/nav.js](ui/js/core/nav.js).

### Lifecycle of one check-in

```
1. User stands at the camera, presses Enter (or waits, then clicks Scan).
2. Browser captures one frame, base64-encodes it, POSTs to /api/auth.
3. Server runs face_engine.extract_embedding(). DeepFace runs ArcFace
   and returns 512 floats.
4. Server runs face_engine.find_match(). It computes cosine distance
   against every stored variant of every user, picks the minimum, and
   if it's below 0.55 returns the user_id and name.
5. Server replies { matched: true, user_id, name, status, low_confidence }
   and stashes a 30-second pending_toggle token in the Flask session.
6. UI moves to "confirmation" state. User presses Enter to confirm.
7. Browser POSTs /api/toggle { user_id, check_in_method: 'face' }.
8. Server runs attendance.toggle_entry(). It flips User.status, opens
   or closes a Session row, and writes an AuditLog row.
9. Server runs integrations.slack.update_status_board(). It edits the
   daily Slack message.
10. UI moves to "success" state, shows "Welcome, <name>!", and resets
    to idle after 3 seconds.
```

---

## 3. Repository Layout

See the tree in [README.md → Project Layout](README.md#project-layout). The rest of this guide assumes that overview.

A few facts worth pinning down up front:

- Five API blueprints: `auth`, `attendance` (auth + toggle + presence + session edits), `users`, `stats`, `admin`. See [§4.5](#45-api-blueprints) for the full endpoint table.
- Five service modules: `attendance`, `users`, `points`, `stats`, `audit`. See [§4.4](#44-services--per-file-deep-dive).
- Three DB tables: `users`, `sessions`, `audit_logs`. See [§4.3](#43-database-models).
- `isel/utils.py` is a single flat module. It holds the `admin_required` decorator, `decode_image` / `ImageDecodeError`, and the `ok()` / `fail()` JSON helpers.
- Frontend has no build step. Everything is vanilla JS loaded via `<script>` tags at the bottom of [ui/index.html](ui/index.html).

### Where to add new code

- **New page or section in the UI?** Add markup to `ui/index.html`, add a JS module under `ui/js/dashboard/`, add a `<script>` tag at the bottom of `index.html`.
- **New API endpoint?** Pick the right blueprint in `isel/api/`, or create a new one and register it in `isel/api/__init__.py`.
- **New business logic?** It goes in `isel/services/`. API code should never import models or build queries directly.
- **New DB column?** Edit `isel/db/models.py` and run `python seed_db.py` to recreate. We have no migration framework. At our scale, drop and re-seed is fine for dev.

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
   │                    Opens its own DB session via session_scope().
   ▼
isel/db/models.py ──►  SQLAlchemy ORM models.
```

**Iron rule.** API code never imports from `isel.db.models` and never runs queries directly. It always goes through a service function. This keeps the API thin.

The only exceptions are `isel/api/attendance.py` (uses `current_app.config['FACE_ENGINE']`) and `isel/api/users.py` (imports the `VARIANT_KEYS` constant). Both are legitimate because they need the constants, not the data.

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
    app.config['TEMPLATES_AUTO_RELOAD'] = True   # Edit index.html, no restart
    app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB request cap

    @app.errorhandler(ImageDecodeError)          # Catch oversize images globally
    def _image_decode_error(err):
        return jsonify({'matched': False, 'success': False, 'message': str(err)}), 400

    @app.errorhandler(ApiError)                  # Services raise these
    @app.errorhandler(HTTPException)             # 404 / 405 under /api/
    @app.errorhandler(Exception)                 # Anything else: log + generic 500
    ...                                          # all answer in JSON for /api/

    from isel.db import init_db
    init_db()                                    # CREATE TABLE IF NOT EXISTS

    from isel.face_engine import FaceEngine
    from isel.services.users import get_all_embeddings
    app.config['FACE_ENGINE'] = FaceEngine(get_all_embeddings)
    # ^^^ Heavy. Loads DeepFace + TensorFlow into memory (~500 MB).
    #     ArcFace recogniser loads at startup (~10 s).
    #     RetinaFace detector loads lazily on the first /api/auth call (~5 s,
    #     ~50 MB one-time download). Total cold start ~15 s.
    #     Done ONCE per process. Never create FaceEngine per request.

    from isel.api import register_blueprints
    register_blueprints(app)

    start_scheduler(app.config['DAY_RESET_HOUR'])  # nightly auto-checkout (in-app)

    @app.cli.command('auto-checkout')            # `flask auto-checkout` CLI (fallback)
    def _cli_auto_checkout():
        from isel.services.attendance import auto_checkout_all
        auto_checkout_all()

    @app.get('/')
    def index():
        return render_template('index.html')

    return app
```

**Production** uses [wsgi.py](wsgi.py) which calls `create_app('prod')`. `ProdConfig.__init__` raises `RuntimeError` if `FLASK_SECRET_KEY` or `ADMIN_PIN` is missing. This is intentional. Do not bypass it. Set the env vars.

### 4.3 Database models

[isel/db/models.py](isel/db/models.py) defines three tables. There are no migrations. We use `create_all` and drop / reseed for schema changes.

**`users`**

| Column | Type | Notes |
|---|---|---|
| `user_id` | INT PK | auto-increment |
| `name` | VARCHAR(255) | display name; indexed |
| `user_type` | VARCHAR(50) | one of `先生` · `PhD` · `M2` · `M1` · `B4` · `Intern` · `卒業` (free-text, not enforced) |
| `embedding` | JSON | face data. See [section 5.2](#52-the-3-variant-slot-system) for the shape. |
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
| `target_user_id` | INT | user affected (not a real FK; see below) |
| `target_name` | VARCHAR(255) | name snapshot at time of action |
| `performed_by` | VARCHAR(50) | `admin` · `check-in` · `system` |
| `timestamp` | DATETIME | indexed |

**Why `target_name` is denormalized on `audit_log`.** If you delete a user, their audit history must remain readable. Joining to `users` would break. Storing the name at write time is the simplest fix. The trade-off is that renames do not propagate (you will see the old name in old log entries). This is the correct behavior. History should reflect what was true at the time.

### 4.4 Services per-file deep dive

**Every service function opens its DB session through `session_scope()`** from [isel/db/__init__.py](isel/db/__init__.py). It is a context manager that commits on success, rolls back and re-raises on error, and always closes the session. Reads use it too (the commit is a no-op). Functions that need to reject a request raise `ApiError(message, status)` from [isel/utils.py](isel/utils.py) instead of returning `{'success': False, ...}`; the app-wide handler turns that into JSON, and `session_scope` still rolls back on the way out. Anything else that escapes a service is a bug: it is logged with a traceback and reported as a generic 500. **You should never call `SessionLocal()` directly in service code.** Use the context manager.

#### `isel/services/users.py`

The biggest service file. Handles registration, CRUD, face variant storage, and promotions.

Key constants:
```python
VARIANT_KEYS = ('normal', 'glasses', 'mask')
MAX_FRAMES_PER_VARIANT = 3
```

Key functions:

- **`_normalize_variants(stored)`.** The single guard for the `{variant_key: [vec, ...]}` shape. Drops keys not in `VARIANT_KEYS`, drops empty slots, caps each slot at `MAX_FRAMES_PER_VARIANT`. Returns `{}` for `None` or empty input. Read paths (`get_all_users_info`, `get_all_embeddings`) and the write path (`set_face_variant`) all go through it so the shape stays consistent on the way in and out.

- **`register_user(name, user_type, variants) → int`.** Creates a `User` row. `variants` must be a `{variant_key: [vec, ...]}` dict. Normalised through `_normalize_variants` before insert. Returns the new `user_id`.

- **`set_face_variant(user_id, variant_key, frames) → dict`.** Replaces one slot (e.g. just `glasses`) without touching the others. Caps at 3 frames. Returns `{success, variants: [...]}` listing which slots are now populated.

- **`get_all_embeddings() → dict`.** Powers `FaceEngine.find_match`. Returns `{user_id: {name, variants: {normal: [...], glasses: [...]}}}`. Called on every check-in. This is fine. We read it once per request and the queries are millisecond-scale.

- **`get_all_users_info() → list[dict]`.** Powers the Members tab. Returns per-user metadata including `face_variants: ['normal', 'glasses']` (which slots are populated). `last_seen` is the most recent `checked_out_at` of any session.

- **`promote_students(promotions) → dict`.** Applies an explicit list `[{user_id, new_type}, ...]`. All-or-nothing transaction. Writes `PROMOTE` audit rows. **Why explicit-only:** the user explicitly rejected automatic promotion chains because PhD branching makes them ambiguous (B4 can become M1 *or* graduate, M2 can become PhD *or* graduate). The frontend wizard ([ui/js/dashboard/modals.js](ui/js/dashboard/modals.js)) walks the admin through each student before submission.

#### `isel/services/attendance.py`

Toggle-based. Check-in and check-out share one function.

- **`toggle_entry(user_id, check_in_method='face') → dict`.** If user is OUT, opens a new `Session` row and sets `status=True`. If IN, sets `status=False` and closes the open session. Always writes an `AuditLog` row with `performed_by='check-in'`. Returns `{user_id, name, event_type: 'IN' | 'OUT', timestamp}`.

- **`auto_checkout_all() → None`.** Closes all open sessions, marks status False on every present user, writes one `AUTO_CHECKOUT` audit row per user, then refreshes the Slack board. Called nightly by the in-app APScheduler job (`isel/jobs/scheduler.py`) at `DAY_RESET_HOUR` Asia/Tokyo; also exposed as the `flask auto-checkout` CLI fallback.

- **`_close_stale_session(session, user_id, now)`.** Internal safety net. If a session has been open more than 24h, it is almost certainly forgotten. Closes it lazily on the user's *next* check-in and writes a `STALE_SESSION_CLOSED` audit row. This means missing one scheduler tick is non-catastrophic.

- **`get_present_users_detailed() → list[dict]`.** Returns currently-present members with `{id, name, type, duration}` for the bottom presence strip.

#### `isel/services/points.py`

Pure SQL aggregations. No business logic to speak of. The rule: **1 point = 1 calendar day with at least one check-in.**

- **`current_academic_year(today=None) → int`.** Returns the AY containing today. `today.year` if month is 4 or greater, else `today.year - 1`. AY 2026 means April 1, 2026 to March 31, 2027.

- **`monthly_leaderboard(year, month) → list[dict]`.** Ranks members by distinct days present in the calendar month.

- **`academic_year_leaderboard(ay_year) → list[dict]`.** Same, scoped to `[ay_year-04-01, (ay_year+1)-04-01)`. **Half-open interval.** Mar 31 belongs to the previous AY.

Both use `func.count(func.distinct(func.date(LabSession.checked_in_at)))` for the day counting. Cheap query. Runs in under 10 ms on a decade of data.

#### `isel/services/stats.py`

Heavier read-side aggregations powering the dashboard.

- **`daily_log(date_str=None) → list[dict]`.** All IN / OUT events for one calendar day, newest first.
- **`monthly_user_stats(year, month) → list[dict]`.** Per-user `sessions` and `total_minutes` for the month.
- **`weekly_checkin_counts() → list[dict]`.** 7-day trend of unique check-ins (one bar per day).
- **`today_unique_checkins() → int`**, **`active_days_this_month() → int`.** Overview stat cards.
- **`get_user_profile(user_id) → dict`.** Powers the profile modal. Month-to-date stats plus 10 recent sessions.
- **`export_monthly_csv(year, month) → list[dict]`.** Rows for the CSV download.
- **`weekly_grid(start_date, user_ids) → list[dict]`.** The GitHub-style attendance grid (rows = members, cols = 7 days). Each cell carries `total_minutes`, `sessions`, `has_anomaly`. **Anomaly heuristic:** session over 12 h, or method equals `auto_checkout`.
- **`anomalies(days=7) → list[dict]`.** Per-user counters (missing weekdays, long sessions).

#### `isel/services/audit.py`

Two functions only.

- **`record(action_type, target_user_id, target_name, performed_by='admin')`.** Write one row. Most services call this directly after their main commit.
- **`recent_entries(limit=200, user_id=None, user_ids=None, action_types=None, start=None, end=None, q=None) → list[dict]`.** The query interface. Powers the Activity Log tab and CSV export. All filters are optional and AND-ed together. `q` is a case-insensitive `LIKE` against `target_name` OR `action_type`.

### 4.5 API blueprints

[isel/api/__init__.py](isel/api/__init__.py) registers five blueprints in `register_blueprints(app)`:

```python
from isel.api import auth, attendance, users, stats, admin
for mod in (auth, attendance, users, stats, admin):
    app.register_blueprint(mod.bp)
```

The `attendance` blueprint owns every attendance-flow route: `/api/auth`, `/api/toggle`, `/api/present`, `/api/present-detailed`, and `/api/session/<id>`.

#### Complete endpoint reference

| Method | Path | Auth | Blueprint | Behavior |
|---|---|---|---|---|
| POST | `/api/admin/login` | (none) | auth | PIN check with HMAC compare + 5-fails-per-IP / 60-s lockout |
| POST | `/api/admin/logout` | admin | auth | Clear session |
| GET | `/api/admin/status` | (none) | auth | `{authenticated: bool}` |
| POST | `/api/auth` | (none) | attendance | Match a face. Body: `{images: [b64, ...]}` (3-frame burst from the kiosk). Returns `{matched, user_id, name, status, low_confidence}`. Stashes a 30-s `pending_toggle` token in session. |
| POST | `/api/toggle` | (none) | attendance | Flip presence. Validates the `pending_toggle` token (skipped for `check_in_method='manual'`). Triggers Slack update. |
| POST | `/api/register` | admin | users | Create new user with up to 3 variants. Rejects duplicates by face. |
| GET | `/api/users` | (none) | users | All users with `{id, name, type, status, has_face, face_variants, last_seen}` |
| GET | `/api/user/<id>/profile` | (none) | users | Profile plus monthly stats plus 10 recent sessions |
| PUT | `/api/user/<id>` | admin | users | Update name and user_type |
| DELETE | `/api/user/<id>` | admin | users | Delete user (sessions kept; audit log preserved via `target_name` snapshot) |
| POST | `/api/user/<id>/face` | admin | users | Replace one variant slot `{variant, images: [b64, ...]}` |
| PUT | `/api/session/<id>` | admin | attendance | Edit session timestamps |
| GET | `/api/present` | (none) | attendance | List of present names |
| GET | `/api/present-detailed` | (none) | attendance | List with id / type / duration |
| GET | `/api/log/today` | (none) | stats | Today's IN / OUT events |
| GET | `/api/log?date=YYYY-MM-DD` | (none) | stats | Events for a specific date |
| GET | `/api/stats/today` | (none) | stats | `{unique_checkins, active_days_month}` |
| GET | `/api/stats/weekly` | (none) | stats | 7-day check-in trend |
| GET | `/api/stats/weekly-grid?start=&user_ids=` | (none) | stats | Per-user × per-day attendance grid |
| GET | `/api/stats/monthly?year=&month=` | (none) | stats | Per-user sessions and minutes for the month |
| GET | `/api/stats/anomalies?days=N` | (none) | stats | Anomaly counters |
| GET | `/api/export/csv?year=&month=` | admin | stats | Download month's sessions as CSV |
| GET | `/api/stats/points?year=&month=` | (none) | admin | Monthly leaderboard |
| GET | `/api/stats/points/year?year=` | (none) | admin | Academic-year leaderboard `{year, leaderboard}` |
| GET | `/api/audit/log` | admin | admin | Filtered audit log |
| GET | `/api/audit/export.csv` | admin | admin | Audit log as CSV (10 k row cap) |
| POST | `/api/admin/promote-students` | admin | admin | Apply explicit promotion batch |

#### Common patterns

- **Auth gate.** Admin routes use the `@admin_required` decorator from [isel/utils.py](isel/utils.py). Returns 403 if `session.get('admin')` is falsy.
- **Response helpers.** Routes use `ok(message?, **extra)` and `fail(message, status=400, **extra)` from [isel/utils.py](isel/utils.py) for the standard `{success, message?, ...}` JSON shape. Routes that pass a service-result dict straight through (where the service already returns `{success, ...}`) keep `jsonify(result)` because the shape is already correct.
- **Global error handler.** `ImageDecodeError` raised by [isel/utils.py](isel/utils.py) is caught in `app.py` and turned into a 400 JSON response. Route code does not have to wrap every `decode_image()` call.
- **Image size limits.** `MAX_CONTENT_LENGTH = 8 MB` at the Flask layer (rejected at request parse time), plus `_MAX_IMAGE_BYTES = 5 MB` per image in `decode_image()`.
- **Session-stashed pending toggle.** `/api/auth` puts `{user_id, expires}` in the Flask session under `pending_toggle`. `/api/toggle` requires it to match (for the face flow) before flipping state. This prevents a malicious client from POSTing a toggle for someone else's user_id.

---

## 5. Face Recognition Pipeline

This is the part new developers are most nervous about. It is actually simpler than it looks because **all the ML lives in one file** ([isel/face_engine.py](isel/face_engine.py), 54 lines).

### 5.1 Why ArcFace + RetinaFace

DeepFace is a Python wrapper around several face-recognition models. Two choices to know about.

**Recognition model: ArcFace.** Reasons:

1. It returns a 512-dim embedding (lots of discrimination capacity).
2. Cosine distance between two embeddings of the same person is reliably below 0.5 under our lighting.
3. It is fast. About 200 ms per frame on CPU.

We do not fine-tune. Out-of-the-box pretrained weights work well enough for a roster of about 15 people.

**Detector backend: RetinaFace** (passed to `DeepFace.represent` as `detector_backend='retinaface'`). The default is `opencv`, which is the weakest option and frequently misses faces under non-ideal lighting. Retinaface is the gold standard for face localisation. First call after app start triggers a one-time ~50 MB model download (cached after). Total cold start with both models is roughly 15 s.

If retinaface ever causes problems in production, the next best fallback is `mtcnn` (also bundled with DeepFace, faster, slightly weaker on extreme poses).

### 5.2 The 3-variant slot system

Each user can store embeddings under three named slots:

| Slot | Captured with | Optional? |
|---|---|---|
| `normal` | Plain face, no glasses, no mask | **No.** Required for registration. |
| `glasses` | Wearing glasses | Yes |
| `mask` | Wearing a mask | Yes |

Each slot holds up to 3 embeddings (burst capture, 3 frames in ~1 second). Total cap: **9 embeddings per user.**

#### Storage shape on `User.embedding` (JSON column)

```json
{
  "normal":  [[0.012, -0.443, ...], [0.014, -0.441, ...], [0.011, -0.440, ...]],
  "glasses": [[0.021, -0.330, ...]],
  "mask":    []
}
```

#### One shape, one guard

Embeddings are always stored and read as the dict shape above. `_normalize_variants` in [isel/services/users.py](isel/services/users.py) is the single guard. It drops invalid keys, drops empty slots, and caps each slot at `MAX_FRAMES_PER_VARIANT`. Both writes (`set_face_variant`, `register_user`) and reads (`get_all_embeddings`, `get_all_users_info`) call it. Direct indexing like `user.embedding['normal']` is fine in your own code as long as you go through that helper at the boundary.

### 5.3 The matching algorithm

`FaceEngine.find_match(probe_vec, threshold)` in [isel/face_engine.py](isel/face_engine.py):

```
1. For every user (via get_all_embeddings()):
     For every variant of that user:
       For every stored vector in that variant:
         dist = cosine(probe_vec, stored_vec)
         if dist < min_so_far:
           min_so_far = dist
           best_user_id = user_id
2. Return (best_user_id, best_name, min_so_far). Or (None, None, None)
   if no candidate beat the threshold.
```

It is a brute-force scan. With 15 users × 9 variants × ~200 ns per cosine, that is **under 30 μs total per match**. We do not need an ANN index until we have thousands of faces.

**Multi-frame matching: `find_best_match(embeddings, threshold)`.** The kiosk captures 3 frames per scan (via `captureBurst`) and POSTs them all to `/api/auth`. The server runs `find_best_match`, which fetches the registered embedding set once and scans all probe frames against it in a single pass, returning the closest match. This catches the case where one frame in the burst is a blink or motion blur. Cost is small (3× the inner loops, still under 100 μs total).

**Extending the algorithm.** Both `find_match` and `find_best_match` delegate to the private `_closest(targets, registered, threshold)`, so a distance-metric or tie-break change is made once, there. Callers (just `isel/api/attendance.py` and `isel/api/users.py`) treat the engine as an opaque oracle that returns `(user_id, name, distance)`.

### 5.4 Thresholds

| Constant | Value | Where set | What it gates |
|---|---|---|---|
| `auth_threshold` | 0.55 | `FaceEngine.__init__` | Whether a check-in face counts as a match (cosine distance must be below this) |
| `reg_threshold` | 0.50 | `FaceEngine.__init__` | Whether a new registration is rejected as a duplicate of an existing user. Stricter, because we want to be sure before refusing to register. |
| `LOW_CONFIDENCE_THRESHOLD` | 0.40 | env var (`.env`) | UI's "low confidence" badge. Shown when match distance is between this and `auth_threshold`. |

**Important distinction.** `LOW_CONFIDENCE_THRESHOLD` is purely cosmetic. It controls the badge in the UI. The actual match decision uses `auth_threshold` (0.55). Changing the env var does **not** change which faces are accepted.

If you change the camera or move it to a different lighting environment, re-tune these:

1. Register a few people.
2. Add a few `print(dist)` calls in `find_match`.
3. Watch values in the console as you check in and out across a day.
4. Pick a threshold about 0.05 above the worst legitimate match.
5. Remove the `print` calls. Update this guide's table with the new value plus a rationale.

### 5.5 Registration flow, the 3-step wizard

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

- `REG_STEPS`. The wizard config (label, key, required flag per step).
- `_renderRegStep()`. Draws the current step into the modal.
- `onRegStepCapture()` / `onRegStepSkip()`. Step navigation.
- `_submitRegistration()`. Packages all collected base64 frames and POSTs.

`captureBurst(videoId, count=3, gapMs=350)` lives in [ui/js/core/camera.js](ui/js/core/camera.js) next to `captureFrame`. Both the registration wizard and the kiosk scan use it. On the kiosk, each captured frame triggers a brief pulse on the face-box corner brackets so the user has a concrete "a photo was just taken" cue (see Wait-time UX below).

**Wait-time UX.** The full burst plus 3 ArcFace embedding extractions takes a few seconds on CPU. To keep that wait from feeling stuck:

- The kiosk scanning state in [ui/js/checkin/state-machine.js](ui/js/checkin/state-machine.js) cycles its sub-text every 400 ms through realistic phases (`Capturing frame 1 of 3 → Detecting → Matching → Almost done`). The interval is started in `setState('scanning')` and torn down by every other `setState(...)` call.
- The registration modal shows `Processing` followed by animated dots and a rotating spinner. Both come from CSS only (`.processing-dots` and `.spinner` in [ui/css/base.css](ui/css/base.css)), so the JS just sets one `innerHTML` and the browser handles the animation.
- `_flashCorners` in [ui/js/core/camera.js](ui/js/core/camera.js) pulses the four face-box corner brackets on the kiosk (scale + opacity) for ~220 ms per captured frame. The registration modal has no face-box and intentionally gets no pulse; its existing "Capturing Normal…" text covers that case.

None of these change actual latency. They only change how the wait feels.

**Per-slot retake** for existing users uses the same modal but targets one slot only (`/api/user/<id>/face` with `{variant, images}`).

---

## 6. Frontend Architecture

### 6.1 Conventions

- **All JS files are IIFE-wrapped** (`(function () { ... })();`). This keeps module-private variables off `window`.
- **Public functions are exposed via `window.foo = function foo() { ... }`** so inline HTML `onclick=` handlers can find them. Yes, we use inline handlers. They are easy to read, you can `Cmd+F` them, and we have no build step to add an event-listener layer.
- **No build step, no bundler.** Files load in fixed order from `<script>` tags at the bottom of [ui/index.html](ui/index.html). To remove dead code, just delete it. Nothing is going to tree-shake for you.
- **Vanilla JS only.** No React, no Vue, no jQuery. Reason: this codebase needs to survive 10+ years of student turnover. Every framework we pick today will probably be deprecated by 2030. The DOM API will not be.
- **One file = one concern.** When a JS file passes ~300 lines, split it.

### 6.2 File map

| File | Purpose |
|---|---|
| [ui/index.html](ui/index.html) | Single-page shell. Top nav, check-in markup, dashboard markup (4 tabs), all modals. ~485 lines. Both screens swap via `.screen.active`. |
| [ui/css/tokens.css](ui/css/tokens.css) | CSS variables only (colors, spacing). Re-skin the app by editing this file. |
| [ui/css/base.css](ui/css/base.css) | Reset, topbar, modals, shared buttons. |
| [ui/css/checkin.css](ui/css/checkin.css) | Kiosk screen styles. |
| [ui/css/dashboard.css](ui/css/dashboard.css) | Dashboard styles. Largest file (~900 lines). |
| [ui/js/core/utils.js](ui/js/core/utils.js) | Escape helpers (`esc`, `escAttr`); `fmtMins`; fetch wrapper `api.get` / `api.post` / `api.put` / `api.delete`; top-bar clock; shared member-display helpers (`avColor`, `initials`, `avatarHtml`, `isGraduated`, `roleBadgeClass`, `formatLastSeen`); date helpers (`mondayOf`, `isoDate`) and the `byPresenceThenName` sort; modal helpers `openModal(id)` / `closeModal(id)` / `anyModalOpen()` / `closeModalOnBg(event, closer)`; list-rendering helper `renderList(el, items, template, empty?)`. |
| [ui/js/core/camera.js](ui/js/core/camera.js) | `startCamera(videoId)` / `stopCamera()` / `captureFrame(video) → base64` / `captureBurst(video, count=3, gapMs=350) → [base64, ...]`. |
| [ui/js/core/nav.js](ui/js/core/nav.js) | `switchScreen()` plus global `C` / `D` keyboard shortcuts. Calls `anyModalOpen()` to suppress shortcuts when a modal is open. |
| [ui/js/core/cohort-multiselect.js](ui/js/core/cohort-multiselect.js) | Multi-select with preset buttons (All / 先生 / M2 / M1 / B4 / Intern / 学生). Smart popover positioning (flips when overflowing viewport). |
| [ui/js/checkin/index.js](ui/js/checkin/index.js) | Bootstraps the kiosk screen + keyboard handlers + `loadMemberStrip` (bottom presence strip). |
| [ui/js/checkin/state-machine.js](ui/js/checkin/state-machine.js) | `idle` / `scanning` / `confirmation` / `fail` / `success` rendering. |
| [ui/js/checkin/manual-picker.js](ui/js/checkin/manual-picker.js) | Modal for picking a member manually when face match fails. |
| [ui/js/dashboard/index.js](ui/js/dashboard/index.js) | Tab dispatcher (`switchDashTab`) + 30 s polling + `1`/`2`/`3`/`4` shortcuts. |
| [ui/js/dashboard/overview.js](ui/js/dashboard/overview.js) | Stat cards + 7-day trend chart + activity log section. |
| [ui/js/dashboard/attendance.js](ui/js/dashboard/attendance.js) | Monthly and academic-year leaderboards. |
| [ui/js/dashboard/attendance-grid.js](ui/js/dashboard/attendance-grid.js) | Weekly GitHub-style grid. |
| [ui/js/dashboard/activity.js](ui/js/dashboard/activity.js) | Audit log with filters and CSV export. |
| [ui/js/dashboard/members.js](ui/js/dashboard/members.js) | Member list with edit / delete / promote actions. |
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

Defined in [ui/js/checkin/state-machine.js](ui/js/checkin/state-machine.js). Each state has a config object (`tagClass`, `tagText`, `name`, `sub`, `faceClass`, `scanLine`, `card`, `btnText`, `btnDisabled`, `hints`) and `setState(key, data)` applies all of them in one call. Any field may be a function of `data` instead of a plain value — that is how `confirmation` and `success` render the member's name.

**Adding a new state.** Add an entry to `CHECKIN_STATES`, then transition into it from wherever makes sense (`setState('mynewstate')`). If the state needs dynamic content, make the varying fields functions of `data` and pass it in: `setState('success', { name, event })`. Always run member-supplied text through `esc()` — these fields land in `innerHTML`.

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

The global `C` / `D` handlers in [ui/js/core/nav.js](ui/js/core/nav.js) call `anyModalOpen()` first and bail if any modal is showing. Otherwise `D` would switch screens out from under an open Add Member modal.

### 6.4 Dashboard tabs

Four tabs: `overview` (1), `attendance` (2), `members` (3), `activity` (4). Defined by `<div class="db-page" id="db-<name>">` blocks in [ui/index.html](ui/index.html). Only one has class `active` at a time.

`switchDashTab(name, btn)` in [ui/js/dashboard/index.js](ui/js/dashboard/index.js) handles the swap. For `members` and `activity`, it first calls `checkAdminAndProceed(...)` which gates behind PIN entry if not already authenticated.

`loadDashboard()` is called on initial screen-switch and then re-run every 30 s by `setInterval`. It calls `loadOverview()`, `loadLogSection()`, and `loadMembers()` in parallel. Tab-specific data (attendance leaderboards, activity log) loads only when that tab is switched to.

**There is no formal `init` / `destroy` lifecycle per tab.** The simpler dispatcher above has been sufficient. If a future tab needs cleanup (e.g. a websocket), introduce that lifecycle then. Do not add it preemptively.

### 6.5 Modals

All modals are direct children of `<body>`, hidden by default with class `hidden`, shown by removing that class. IDs: `reg-modal` / `pin-modal` / `profile-modal` / `face-rereg-modal` / `context-modal` / `promote-modal` / `picker-modal`.

Use `openModal(id)` and `closeModal(id)` from [ui/js/core/utils.js](ui/js/core/utils.js) instead of toggling `classList` by hand. `anyModalOpen()` returns true if any of the seven known modal IDs are visible. Global keyboard handlers consult it to suppress shortcuts. Adding a new modal? Add its id to `_MODAL_IDS` in [ui/js/core/utils.js](ui/js/core/utils.js).

---

## 7. Configuration & Environments

Environment variables: see the table in [README.md → Configuration](README.md#configuration). `.env` is loaded by `python-dotenv` at the top of [app.py](app.py).

[config.py](config.py) defines four classes:

| Class | When | Notes |
|---|---|---|
| `Config` | base | Loads all env vars with safe defaults |
| `DevConfig` | `create_app('dev')` (default) | `DEBUG=True`, cookies not secure |
| `ProdConfig` | `create_app('prod')` (via `wsgi.py`) | `DEBUG=False`, cookies secure. **Raises `RuntimeError` if `FLASK_SECRET_KEY` or `ADMIN_PIN` is missing.** |
| `TestConfig` | `create_app('test')` (tests) | In-memory SQLite, fixed test PIN/secret |

`TestConfig` is the one place env vars do not apply. It hard-codes `sqlite:///:memory:`, a fixed PIN, and a fixed secret so tests are reproducible across machines.

---

## 8. Slack Integration

Slack is a hard requirement in production. The integration has two surfaces:

1. **Daily status board.** One Block Kit message per day in the channel set by `SLACK_CHANNEL` (default `#a-lab-status`), edited in place via `chat.update` whenever presence changes.
2. **`/who` and `/points` slash commands.** `/who` returns the current present-list. `/points` returns the top 5 of this month's leaderboard with 🥇🥈🥉 medals for the top three. Both reply ephemerally (only visible to the runner). Delivered via Socket Mode, so no public HTTP endpoint is needed.

The full file is [isel/integrations/slack.py](isel/integrations/slack.py), about 130 lines.

### Status board format (Block Kit)

```
[header]   🟢 3 in the lab
[section]  • Inoue (M2)
           • Naimi (M1)
           • Yamamoto (B4)
[context]  _Updated 14:32_
```

When empty: a header (`⚫ Lab is empty`) + the context footer; no section block. A short plain-text fallback (`🟢 3 in the lab`) goes alongside `blocks` so push notifications and screen readers still get something sensible.

### How it works

- `slack_state.json` (at repo root, gitignored) caches `{ts, date, channel}` so the next call knows which message to edit.
- On each `update_status_board()`:
  1. Render Block Kit from `get_present_users_detailed()`.
  2. If `state['date'] == today` and channel matches, `chat.update(channel, ts, text, blocks)`.
  3. If Slack replies `message_not_found` (someone deleted it), fall through and post fresh.
  4. Otherwise (new day, or no state) `chat.postMessage(channel, text, blocks)` and save the returned `ts`.
- Any error is caught and logged. **Failures never block check-ins.**

### Socket Mode and the Werkzeug guard

`init()` starts the `SocketModeHandler` on a daemon thread (`name='slack-socket-mode'`). The thread dies cleanly with the main process. The slash command handler runs inside that thread; SQLAlchemy sessions are per-thread (the engine is created with `check_same_thread: False`), so there's no contention with the HTTP threads.

In dev, `flask --app app run` forks a Werkzeug reloader parent that re-execs a child on file change. Without a guard, Socket Mode would connect twice (once per process), wasting a Slack connection and confusing the handlers. [app.py](app.py) only calls `init()` when `WERKZEUG_RUN_MAIN == 'true'` (the child) or when `DEBUG == False` (prod, no Werkzeug). The auto-checkout scheduler in [§9](#9-background-jobs) reuses the exact same guard so it doesn't double-start either.

### Who calls it

- [isel/api/attendance.py](isel/api/attendance.py) after every successful `/api/toggle`.
- [isel/services/attendance.py](isel/services/attendance.py) at the end of `auto_checkout_all()`.
- The `/who` and `/points` handlers in [isel/integrations/slack.py](isel/integrations/slack.py) when a Slack user runs the command. `/who` reuses `get_present_users_detailed`; `/points` reuses `monthly_leaderboard(year, month)` from [isel/services/points.py](isel/services/points.py).

### Setup, once per Slack workspace

1. Create a Slack app at api.slack.com/apps.
2. **OAuth & Permissions** → add bot scopes `chat:write` (status board) and `commands` (slash command).
3. **Socket Mode** → enable it. Generate an App-Level Token with the `connections:write` scope. Copy it (`xapp-...`).
4. **Slash Commands** → create `/who` and `/points`. With Socket Mode on, no request URL is needed; Slack delivers each command over the WebSocket.
5. **Install to Workspace** → copy the bot token (`xoxb-...`).
6. Invite the bot to your status channel: `/invite @YourBot`.
7. Put both tokens in `.env` as `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN`. Optionally set `SLACK_CHANNEL`.
8. Restart the app. Console should show `Slack: bot client initialised` and `Slack: Socket Mode listener started`.

### Dev without Slack

If you don't want to set up a Slack workspace just to hack on the kiosk, leave both tokens empty in dev. `init()` will log `Slack: SLACK_BOT_TOKEN missing; integration disabled` and `update_status_board()` becomes a no-op. The rest of the app runs normally. In **prod**, missing tokens make `ProdConfig.__init__` raise on startup.

---

## 9. Background Jobs

### Auto-checkout

`auto_checkout_all()` closes all open sessions, marks every user OUT, writes `AUTO_CHECKOUT` audit rows, refreshes Slack. Idempotent. Safe to run twice (a second run finds no present users).

It runs **automatically in-app**: [isel/jobs/scheduler.py](isel/jobs/scheduler.py) starts an APScheduler `BackgroundScheduler` from `create_app()` with a `CronTrigger(hour=DAY_RESET_HOUR, minute=0, timezone='Asia/Tokyo')`. The same function is still exposed as `flask auto-checkout` for a manual fallback.

**Why APScheduler now, after we moved off the daemon thread to cron?** The earlier daemon-thread version had three real problems: hard to debug, doubled in dev under Werkzeug's reloader, and left no record it ran. We briefly switched to an OS cron job, but cron has its own footgun — it fires at 22:00 in the *server's* timezone, so a UTC server runs the job at 07:00 JST, and the crontab line is an easy-to-forget manual deploy step (the original reason the 22:00 logout silently never worked). The in-app scheduler fixes all of this:

- **Timezone is pinned to `Asia/Tokyo`** on both the scheduler and trigger, so 22:00 means 22:00 JST regardless of where it runs.
- **APScheduler is event-driven**, not a hand-rolled busy-wait loop — far easier to reason about than the old thread.
- **It reuses the Werkzeug reloader guard** (`_in_werkzeug_reloader_parent` in [app.py](app.py)), so it doesn't double-start in dev.
- **It logs** on boot and on each run, plus the existing `AUTO_CHECKOUT` audit rows.
- Nothing to install on the host. `DAY_RESET_HOUR` is now the *actual* trigger hour (was previously decorative).

### It silently never ran (2026-08-17 post-mortem)

The in-app scheduler then failed the same way cron had, for four separate
reasons. All four are fixed; they are recorded here because each is a trap
worth not re-entering.

1. **Slack could abort startup.** `init_slack()` ran *before* the scheduler
   block, and `slack_bolt`'s `App()` calls `auth.test` during construction — so
   a revoked or rotated bot token raised `BoltError` straight out of
   `create_app()`, taking the whole app down with it. Slack now starts *after*
   the scheduler and is wrapped in `try/except`: it can log a failure, but it
   can never stop check-in, the dashboard, or the nightly job.
2. **The job swallowed its own failures.** `auto_checkout_all()` caught every
   exception and `print()`ed it, so a run that fired and failed was
   indistinguishable from a run that never fired. It now logs and re-raises,
   and `_run_auto_checkout` records the failure in `scheduler.status()`.
3. **The logging was never visible.** Nothing configured the root logger, so
   every `logger.info(...)` in `isel.*` was dropped — including
   "scheduler started". `create_app()` now calls `logging.basicConfig` with
   `LOG_LEVEL` (default INFO), and the scheduler logs at WARNING so it survives
   a quieter setting.
4. **`flask run --no-reload` skipped it silently.** The reloader guard tests
   `WERKZEUG_RUN_MAIN != 'true'`, which is also true when the reloader is
   simply off. Every skip reason is now logged at WARNING, and
   `ENABLE_SCHEDULER=1` forces past the guard.

**Check whether it is armed right now**, in the process actually serving you:

```
GET /api/admin/scheduler      ->  {"running": true, "next_run": "2026-08-17T22:00:00+09:00", ...}
```

`running: false` or a null `next_run` means it will not fire — look for the
`Auto-checkout scheduler NOT started:` warning in the log, which names the
reason. `POST /api/admin/auto-checkout` closes everyone out on demand.

### In-app scheduler vs OS cron — the actual trade-off

We have now been bitten by both, so here is the measured comparison rather than
the argument.

| | In-app APScheduler | OS cron calling `flask auto-checkout` |
|---|---|---|
| Fires when the app is down | No | **Yes** |
| Survives app restart / crash | Only if the app comes back before 22:00 | **Yes** |
| Timezone | Pinned to `Asia/Tokyo` in code | Server-local unless you set `CRON_TZ=Asia/Tokyo` |
| Survives a redeploy | Yes, it is in the code | Only if someone re-adds the crontab line |
| Extra moving parts | None | A crontab entry, and the venv path inside it |
| DB contention | Same process, none | Separate process → SQLite write lock |

On that last row, measured rather than assumed: a second process running
`auto_checkout_all()` **waits** for the web app's write lock and succeeds — it
only fails with `database is locked` if a write is held longer than sqlite3's
5s default (observed failing at 5.2s against a deliberately 12s-long lock).
Real writes here are single-row updates taking milliseconds, and 22:00 is the
quietest moment of the day, so this risk is theoretical. `PRAGMA
journal_mode=WAL` would remove even that if you ever want it.

**Recommendation:** if the app is started with `flask run` (the Werkzeug dev
server, no process supervision), add cron as a safety net — its one real
advantage, firing when the app is not running, is exactly the failure mode that
setup has. Belt and braces, and `auto_checkout_all()` is idempotent so a double
fire is harmless:

```cron
CRON_TZ=Asia/Tokyo
5 22 * * * cd /path/to/isel_room && .venv/bin/flask --app app auto-checkout >> /var/log/isel-autocheckout.log 2>&1
```

Note `22:05`, not `22:00`: let the in-app job go first, and cron only has work
to do on the nights the app missed. The log file is the record that it ran.

**Multiple gunicorn workers:** each worker process would start its own scheduler. The deployment is single-worker (the `FaceEngine` is stateful and loads ~500MB of TensorFlow per process), so this isn't normally a concern. If you do scale out, set `ENABLE_SCHEDULER=0` on the extra workers and `=1` on one dedicated process. Even a double-fire is harmless because `auto_checkout_all()` is idempotent.

**Kiosk-activity guard dropped.** The old thread skipped checkout if the kiosk had been touched in the last 15s. That guard depended on `get_last_kiosk_activity()`, which no longer exists. At 22:00 closing time the risk is negligible, and `_close_stale_session` is the backstop anyway.

If the scheduler ever misses a tick, no big deal. `_close_stale_session` in `attendance.py` closes any session open more than 24h the next time that user checks in.

---

## 10. Testing

### Stack

- `pytest`
- `pytest-flask`
- **In-memory SQLite per test** (via `StaticPool` in [tests/conftest.py](tests/conftest.py)). Tests are fast and isolated.

### Fixtures

| Fixture | Scope | What it gives you |
|---|---|---|
| `app` | session | A `create_app('test')` instance |
| `client` | function | `app.test_client()` for HTTP calls |
| `admin_client` | function | `client` already logged in with the test PIN |
| `db_session` | function | A direct SQLAlchemy session for test setup |
| `_clean_db` | autouse | Truncates all tables after each test |
| `frozen_now` | function | Pins `datetime.now()` / `date.today()` inside `isel/services/stats.py` (see below) |

**`frozen_now`** exists because several functions in `isel/services/stats.py`
(`today_unique_checkins`, `active_days_this_month`, `weekly_checkin_counts`,
`get_user_profile`, `anomalies`) read the clock directly instead of taking a
date. Without it those tests would give different answers depending on the day
you run the suite. If you add a function there, prefer taking a date argument —
then you will not need the fixture at all.

### The frontend check

The frontend has no build step and no test runner, so the shared helpers in
`ui/js/core/utils.js` and the kiosk state machine have a plain Node assertion
script instead. Node built-ins only — nothing to install:

```bash
node tests/check_ui.js
```

It runs those files against a minimal DOM stub and asserts the avatar/date/sort
helpers, the modal backdrop handler, and all five kiosk states including that
member names are HTML-escaped. Run it after touching either file.

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

Tests that exercise date-window logic must pin dates explicitly. Do not use `date.today()`. Otherwise the test passes 11 months a year and breaks every April. See [tests/test_points.py](tests/test_points.py) for the pattern. Derive `ay = points.current_academic_year()` then build datetimes like `datetime(ay, 4, 10, ...)`.

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

1. **Pick a blueprint.** Session edits live in `isel/api/attendance.py`, but this endpoint is keyed by user. Put it in `isel/api/users.py`.
2. **Add a service function.** In `isel/services/stats.py` (or whichever fits), write:
   ```python
   from isel.db import session_scope
   from isel.db.models import LabSession

   def get_user_sessions(user_id: int, limit: int = 50) -> list[dict]:
       with session_scope() as session:
           rows = session.execute(...).scalars().all()
           return [{'id': r.id, ...} for r in rows]
   ```
   Always use `with session_scope() as session:`. Never call `SessionLocal()` and try / finally by hand.
3. **Wire the route.**
   ```python
   # isel/api/users.py
   from isel.utils import fail

   @bp.get('/api/user/<int:user_id>/sessions')
   def get_user_sessions(user_id: int):
       if user_id <= 0:
           return fail('user_id must be positive')
       from isel.services.stats import get_user_sessions as svc
       return jsonify(svc(user_id))
   ```
   For validation errors use `fail('message', status=400)`. For success replies that need a `{success: True}` shape, use `ok(message?, **extra)`. Routes that pass a service-result dict straight through keep `jsonify(result)` because the shape is already correct.
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
       renderList('reports-content', data,
         item => `<div class="report-row">${esc(item.name)}</div>`,
         '<div class="log-empty">No reports yet</div>');
     };
   })();
   ```
   `renderList` from [ui/js/core/utils.js](ui/js/core/utils.js) is the standard way to fill a container with list content. It handles the empty-list case for you.
3. **Add `<script>` tag** at the bottom of [ui/index.html](ui/index.html).
4. **Wire the tab dispatcher** in [ui/js/dashboard/index.js](ui/js/dashboard/index.js):
   - Add to `PAGE_META`: `reports: { title: 'Reports', subtitle: '...' }`.
   - Add to `tabMap`: `'5': { name: 'reports', btnId: 'sbt-reports' }`.
   - Add a branch in `switchDashTab` to call `loadReports()`.
5. **Gate behind admin if needed.** Add `name === 'reports'` to the `checkAdminAndProceed` condition.

### 11.3 Change face matching threshold

1. Edit defaults in `FaceEngine.__init__` in [isel/face_engine.py](isel/face_engine.py).
2. Run `python -m pytest tests/test_face_engine.py`. Adjust any threshold-sensitive assertions.
3. Update [section 5.4](#54-thresholds) of this guide with the new value plus a one-line rationale (e.g. "raised to 0.58 after camera replacement").
4. Commit: `fix(face): bump auth_threshold to 0.58 after camera swap`.

### 11.4 Add a new member role

**User types are free-text strings** in `User.user_type`. No enum, no validation.

To add e.g. `Postdoc`:

1. **No code change needed in models.** Just start using the new value.
2. **Update the promotion wizard** in [ui/js/dashboard/modals.js](ui/js/dashboard/modals.js). Add `Postdoc` to the available target types in the wizard step where the admin picks the new role.
3. **Update seed data** in [seed_db.py](seed_db.py) if you want a sample Postdoc to appear in mock data.
4. **Update the cohort filter buttons** in [ui/js/core/cohort-multiselect.js](ui/js/core/cohort-multiselect.js) if you want a one-click "Postdoc" preset.
5. **Update the glossary** in section 1 of this guide.

### 11.5 Debug a face match failure

Symptoms: User stands in front of camera; `/api/auth` returns `{matched: false}`.

1. **Check whether the user has any face data.** Members tab. Look at the row. If the face indicator is off, they need to register.
2. **Try re-registration.** Members tab. That row. Re-Register Face. Capture all 3 variants in good lighting.
3. **Check if `LOW_CONFIDENCE_THRESHOLD` is involved.** If `matched: true` but `low_confidence: true`, the UI is showing the "low confidence" badge. The match still works. If matches are flickering, raise the env var.
4. **Add temporary logging** to `find_match`:
   ```python
   print(f'probe vs {info["name"]} ({_variant_key}): {dist:.3f}')
   ```
   Restart the app, do a few check-ins, watch the console. You will see exactly which stored variants are close and which are far. Remove the print before committing.

### 11.6 Reset the database

```bash
python seed_db.py
```

Wipes everything, creates 11 mock members, ~60 days of session history, ~3 currently-in-lab. Always safe.

If you want a clean DB with no mock data, delete `isel_room.db` and let `init_db()` recreate empty tables on next app start.

---

## 12. Conventions & House Style

A short list. The codebase itself is the canonical example.

- **Commits.** [Conventional Commits](https://www.conventionalcommits.org/). Types we use: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`. Subject in lowercase, no trailing period, imperative voice. Body optional, wrapped at 72.
- **No useless comments.** Default to none. Only write a comment when the *why* is non-obvious (a hidden constraint, a workaround, surprising behavior). Never explain *what* the code does.
- **No dead code.** Delete instead of commenting out. `git log` is the archive.
- **No premature abstractions.** Wait until you have 3 or more real call sites before extracting a helper.
- **Trust internal code.** Validate only at system boundaries (user input, external APIs).
- **Naming.** Python `snake_case` (`PascalCase` classes, `UPPER_SNAKE` constants); JS `camelCase` with `window.foo = function foo() {...}` for inline-handler-exposed functions; CSS `kebab-case`; files `snake_case.py` / `kebab-case.js` / `kebab-case.css`.
- **Japanese in the UI is deliberate.** Identifiers in code are English; UI strings, audit rows, and Slack messages use `先生` / `学生` / `年度` etc.
- **File length.** When a file passes ~400 lines, ask whether it is doing two things. `ui/js/dashboard/modals.js` is on the edge.

---

## 13. Known Limitations & Future Work

| Limitation | Workaround | Future fix |
|---|---|---|
| SQLite single-writer | Fine for 1 lab × ~15 users × decade of sessions | Switch to MySQL via `DATABASE_URL` if scale grows |
| DeepFace + TensorFlow loads ~500 MB at startup (~15 s cold start with the retinaface detector) | Keep the app process running; use `wsgi.py` + gunicorn in prod | Could swap to insightface (smaller) but ArcFace via DeepFace is well-tested for us |
| No multi-tenant support | Run one app instance per lab | Add `lab_id` column on every table. Non-trivial. |
| `ADMIN_PIN` is plaintext in `.env` | Acceptable for kiosk on a trusted network | Hash + per-user admin accounts |
| No password rotation alerting | Manual `.env` update | Maybe a CLI `flask rotate-pin` |
| Mobile dashboard unstyled | Use a tablet or laptop | Responsive CSS rewrite (~2 days work) |
| No CSV import for bulk member registration | Use `seed_db.py` template + edit | Build it if it is ever asked for |
| No browser compatibility tested below Chrome / Firefox / Safari current | (none) | Polyfill / test if needed |

### Candidate next features

- Add Point Systems (Add/Remove Points based on contribution, etc.)

---

## 14. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| App won't start: `RuntimeError: FLASK_SECRET_KEY must be set...` | Running `create_app('prod')` without env vars | Set `FLASK_SECRET_KEY` and `ADMIN_PIN` in `.env`, or use `create_app('dev')` for local |
| App won't start: `ModuleNotFoundError` | Not in venv, or missing dep | `source .venv/bin/activate && pip install -r requirements.txt` |
| Browser console: `switchScreen: missing element for "..."` | Old cached HTML after a Jinja change | Hard refresh (Cmd+Shift+R). If still broken, restart Flask. `TEMPLATES_AUTO_RELOAD=True` is set but Werkzeug sometimes misses changes to `<script>` tag ordering. |
| Face never matches anyone | Lighting, glasses, mask, or stale embeddings | Re-register with all 3 variants in current lighting |
| Face match flicker (matched / not / matched / not) | Distance is right at the threshold | Raise `auth_threshold` slightly or recapture |
| Slack message duplicated | `slack_state.json` got out of sync | Delete `slack_state.json`. Next call will post fresh. |
| Slack errors silently failing | Console shows `Slack: SLACK_BOT_TOKEN is missing` or `Slack status board update failed: ...` | Check `.env`, check bot is in the channel |
| Tests fail in early April | A test used `date.today()` instead of pinning dates | Find the offender; refactor to `points.current_academic_year()` |
| `/api/toggle` returns "No active auth session" | More than 30 s elapsed between `/api/auth` and `/api/toggle` | Scan again. The pending_toggle token expired. |
| Admin login locked out | Too many wrong PIN attempts (5 per IP, resets after 60 s) | Wait 60 s |
| Dev DB out of sync after schema change | No migrations. Drop tables manually. | `python seed_db.py` (or delete `isel_room.db` for empty) |
| Camera permission denied in browser | First-time prompt missed | Click lock icon → site settings → allow camera; or chrome://settings/content/camera |
| Auto-checkout doesn't run | Scheduler never armed, or the job fired and failed | **Start here: `GET /api/admin/scheduler`.** `running: false` or a null `next_run` means it will never fire — the startup log has an `Auto-checkout scheduler NOT started:` warning naming the reason (`TESTING`, `ENABLE_SCHEDULER=0`, or the `--no-reload` reloader guard, which `ENABLE_SCHEDULER=1` overrides). If it *is* armed, check `last_run.error` and the log for `Auto-checkout job FAILED`. Force it with `POST /api/admin/auto-checkout` or `flask auto-checkout`. See the post-mortem in [§9](#9-background-jobs). |
| Kiosk identifies the wrong person | Confusable enrolments, an outlier frame, or a genuinely ambiguous scan | Run `python diagnose_faces.py` **on the lab server** — it reports enrolment counts, whether two enrolled people are within the auth threshold of each other, whether one stored frame attracts every probe, and who a garbage embedding gets reported as. Then read the log: every scan writes `face: matched <name> at <distance> (runner-up <name> at <distance>)`, or `face: AMBIGUOUS, rejected`. A wrong match with a *large* runner-up gap means a bad enrolment (re-enrol that person); a small gap means tighten `FACE_MATCH_MARGIN`. |

---

## 15. Getting Help

When you are stuck:

1. **Re-read the relevant section here.** Often the answer is in the gotcha you skimmed.
2. **`git log -p <file>`.** The commit history explains *why* things are the way they are. Reading recent commits in the area you're modifying is the single best way to absorb context.
3. **Run the tests.** They encode invariants. If you are not sure whether a refactor is safe, `pytest`.
4. **Original team:** _(placeholder, fill in names + contact when handing over)_.
5. **GitHub issues:** _(placeholder, link to the repo's issues tab)_.

### Conventional commits cheat sheet

```
feat:     New feature visible to users
fix:      Bug fix
refactor: Code change that neither fixes a bug nor adds a feature
chore:    Build / tooling / config (no production code)
docs:     Documentation only
test:     Tests only
perf:     Performance improvement
style:    Formatting (no code change)
```

Subject in lowercase, no period, 70 chars or fewer. Optional body wrapped at 72.

---
