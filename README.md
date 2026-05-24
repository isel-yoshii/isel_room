# ISEL 在室管理システム

> Face-recognition-based lab presence tracking for the Intelligent Software Engineering Lab (KIT).

Members check in and out by looking at a camera at the lab door. The sensei gets a live dashboard, weekly attendance grid, monthly and academic-year leaderboards, and a full audit trail. Optional Slack integration keeps the lab Slack channel always up to date with who's in.

---

## Table of Contents

- [Screenshots](#screenshots)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Basic Usage](#basic-usage)
- [Configuration](#configuration)
- [Slack Setup (Optional)](#slack-setup-optional)
- [Project Layout](#project-layout)
- [Testing](#testing)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Screenshots

_Add screenshots once the lab kiosk is in production. Suggested:_

- **Check-in screen** — full-screen kiosk with live camera feed, scan state, and the bottom presence strip.
- **Dashboard overview** — stat cards, 7-day check-in trend, monthly activity chart.
- **Attendance tab** — weekly grid + monthly leaderboard + academic-year leaderboard.

---

## Features

- **Face check-in / check-out** with a 3-variant capture system (normal / glasses / mask) so glasses-on vs glasses-off doesn't trip up recognition.
- **Live presence strip** at the bottom of the kiosk — green dot = currently in, grey = out.
- **Weekly attendance grid** (GitHub-style heat-map) showing who came in which days.
- **Leaderboards** — points are 1-per-day-present, browseable by month or by academic year (`2026年度`). All-time resets every April 1.
- **Member management** — add, edit, delete, re-register faces, and a Promotion Wizard to walk through grade transitions each April.
- **Audit log** — every admin and attendance event recorded, filterable by member / action / date / free-text, exportable as CSV.
- **Slack daily status board** — a single message in your lab channel, edited in place as people come and go (no chat firehose).
- **Auto-checkout cron** — nightly job force-closes any forgotten sessions.
- **Manual fallback** — when face recognition fails, anyone can pick their name from a list.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.10+ |
| Web framework | Flask 3 |
| ORM / DB | SQLAlchemy 2.0, SQLite (dev) / MySQL (prod) |
| Face recognition | DeepFace + ArcFace (512-dim embeddings, cosine distance) |
| Image processing | OpenCV 4, NumPy, SciPy |
| Frontend | Vanilla JavaScript (no build step, no framework) |
| Charts | Chart.js 4 |
| Fonts | Syne, Nunito, IBM Plex Mono |
| Slack | slack-bolt (post-only, no Socket Mode) |

---

## Quick Start

Tested on macOS, Linux, and WSL. Windows native should work but is untested.

### Prerequisites

- Python 3.10 or newer
- A webcam (for kiosk use — the dashboard works fine without one)
- (Optional) Slack workspace + bot token

### Install

```bash
git clone https://github.com/your-org/isel_room.git
cd isel_room
python -m venv .venv
source .venv/bin/activate           # macOS/Linux
# .venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

> The first `pip install` is slow (~3 minutes) because DeepFace pulls in TensorFlow. This is one-time.

### Configure

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```env
FLASK_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
ADMIN_PIN=<choose any string>
```

Leave the rest at defaults for now.

### Seed the database

```bash
python seed_db.py
```

This drops and recreates the DB with 11 mock members and ~60 days of fake attendance history. Re-run any time during development to reset.

### Run

```bash
flask --app app run --host 0.0.0.0 --port 5001
```

Open <http://localhost:5001> in a browser. The Check-in screen loads by default. Press `D` to switch to the Dashboard.

> **Production:** use `wsgi.py` with gunicorn. The auto-checkout job is a CLI command (`flask auto-checkout`) — schedule it via cron, not as part of the web process.

---

## Basic Usage

### As a lab member (at the kiosk)

1. Walk up to the camera.
2. Press `Enter` (or click **Scan Face**).
3. Confirm the match with `Enter`. The screen says "Welcome, <name>!" or "See you, <name>!".

If your face isn't matched, press `Space` to pick your name from a list.

### As the sensei / admin (on the dashboard)

| Key | Tab |
|---|---|
| `1` | Overview — stat cards, charts, recent activity |
| `2` | Attendance — weekly grid + leaderboards |
| `3` | Members — add / edit / delete / re-register (PIN required) |
| `4` | Activity Log — full audit log with filters (PIN required) |

**Add a new member:** Members tab → Add Member → enter name + role → 3-step face capture wizard (Normal required, Glasses and Mask optional). The wizard bursts 3 frames per step for robustness.

**Promote students at year-end:** Members tab → Promote Students → walk through each student in the wizard and pick their new role (M1 → M2, M2 → 卒業 or PhD, etc.). All changes are applied atomically and logged.

### Nightly auto-checkout (cron)

Add to your crontab to force-close forgotten sessions every night at 22:00:

```cron
0 22 * * *  cd /path/to/isel_room && FLASK_APP="app:create_app" flask auto-checkout
```

If you miss a tick, no big deal — any session open over 24 hours is closed automatically on the user's next check-in.

---

## Configuration

All configuration is via environment variables (load via `.env`):

| Variable | Default | Required? | Purpose |
|---|---|---|---|
| `FLASK_SECRET_KEY` | `dev-secret-change-me` | **Yes in prod** | Flask session signing key |
| `ADMIN_PIN` | _(empty)_ | **Yes** | PIN for the admin dashboard |
| `DATABASE_URL` | `sqlite:///isel_room.db` | No | SQLAlchemy connection string |
| `LOW_CONFIDENCE_THRESHOLD` | `0.40` | No | UI badge cutoff for "low-confidence" matches (cosmetic only) |
| `DAY_RESET_HOUR` | `22` | No | Documents your lab's closing hour (the cron is the actual reset trigger) |
| `SLACK_BOT_TOKEN` | _(empty)_ | No | Set to enable Slack integration |

`ProdConfig` (used by `wsgi.py`) refuses to start without `FLASK_SECRET_KEY` and `ADMIN_PIN` — this is intentional.

---

## Slack Setup (Optional)

Posts and edits **one** message per day in your lab channel — not a chat firehose.

1. Create a Slack app at <https://api.slack.com/apps>.
2. Add bot scope: `chat:write`.
3. Install to your workspace, copy the bot token (`xoxb-...`).
4. Invite the bot to your channel: `/invite @YourBotName`.
5. Set `SLACK_BOT_TOKEN` in `.env` and restart the app.

The default channel is `#a-lab-status` — change `_DEFAULT_CHANNEL` in [isel/integrations/slack.py](isel/integrations/slack.py) if needed.

---

## Project Layout

```
isel_room/
├── app.py                  # Flask app factory
├── wsgi.py                 # Production entry point
├── config.py               # Dev / Prod / Test configs
├── seed_db.py              # Reset DB with mock data
├── isel/
│   ├── api/                # Flask blueprints (auth, attendance, users, stats, admin)
│   ├── services/           # Business logic (attendance, users, points, stats, audit)
│   ├── db/                 # SQLAlchemy models + session
│   ├── face_engine.py      # DeepFace ArcFace wrapper
│   ├── integrations/       # Slack status board
│   └── utils.py            # @admin_required decorator + image decoder
├── tests/                  # pytest suite
└── ui/
    ├── index.html          # Single-page shell
    ├── css/                # tokens, base, checkin, dashboard
    └── js/                 # core, checkin, dashboard
```

See [DEVELOPER_GUIDE.md §3](DEVELOPER_GUIDE.md#3-repository-layout) for the annotated tree.

---

## Testing

```bash
python -m pytest
```

Runs the full suite (~21 tests) against an in-memory SQLite. No external services required.

---

## Documentation

For everything beyond getting it running:

- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** — comprehensive architecture, every layer explained, face pipeline deep-dive, frontend module map, state machines, testing patterns, common workflows (recipes), and troubleshooting. Read this on your first day.

---

## Contributing

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(points): academic-year leaderboard resets every Apr 1
fix(ui): rotate avatar colours in kiosk manual picker
refactor(slack): single daily status board updated via chat.update
chore(seed): update members to actual lab roster
docs(guide): document 3-variant face slot system
```

Subject in lowercase, no trailing period. Body optional, wrapped at 72.

Other conventions (no Co-Authored-By lines, comment policy, naming, file-length guidance) are in [DEVELOPER_GUIDE.md §12](DEVELOPER_GUIDE.md#12-conventions--house-style).

---

## License

_Internal use — KIT Intelligent Software Engineering Lab. Add a formal LICENSE file before publishing externally._

---

## Acknowledgments

- Built for the **ISEL Lab** at the Kyoto Institute of Technology.
- Face recognition via [DeepFace](https://github.com/serengil/deepface) (ArcFace).
- Inspired by [GitHub's contribution graph](https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-github-profile/managing-contribution-settings-on-your-profile/viewing-contributions-on-your-profile) for the weekly attendance grid.
