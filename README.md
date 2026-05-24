# ISEL 在室管理システム

> Face-recognition lab presence tracking for the Intelligent Software Engineering Lab (KIT).

Members check in and out by looking at a camera at the lab door. Everyone can see a live dashboard, a weekly attendance grid, monthly and academic-year leaderboards, and a full audit trail. A Slack integration keeps the lab Slack channel up to date with who is in.

---

## Table of Contents

- [Screenshots](#screenshots)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Basic Usage](#basic-usage)
- [Configuration](#configuration)
- [Slack Setup](#slack-setup)
- [Project Layout](#project-layout)
- [Testing](#testing)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Screenshots

_Add screenshots once the lab kiosk is in production. Suggested:_

- **Check-in screen.** Full-screen kiosk with the live camera feed, the scan state, and the bottom presence strip.
- **Dashboard overview.** Stat cards, the 7-day check-in trend, and the monthly activity chart.
- **Attendance tab.** Weekly grid plus the monthly and academic-year leaderboards.

---

## Features

- **Face check-in and check-out** with a 3-variant capture system (normal, glasses, mask). Glasses on vs glasses off does not trip up the match.
- **Live presence strip** at the bottom of the kiosk. Green dot means currently in. Grey means out.
- **Weekly attendance grid** in the GitHub-style heat-map. Shows who came in on which day.
- **Leaderboards.** One point per day present. Browse by month or by academic year (`2026年度`). The all-time count resets every April 1.
- **Member management.** Add, edit, delete, re-register faces. A Promotion Wizard walks the admin through grade transitions each April.
- **Audit log.** Every admin and attendance event is recorded. Filter by member, action, date, or free text. Export to CSV.
- **Slack daily status board + `/who-is-in` slash command.** One Block Kit message per day in your lab channel, edited in place as people come and go (no chat firehose). Anyone in the workspace can run `/who-is-in` for an ephemeral reply with the current present-list.
- **Auto-checkout cron.** A nightly job force-closes any forgotten sessions.
- **Manual fallback.** When face recognition fails, anyone can pick their name from a list.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.10+ |
| Web framework | Flask 3 |
| ORM / DB | SQLAlchemy 2.0, SQLite (dev), MySQL (prod) |
| Face recognition | DeepFace + ArcFace (512-dim embeddings, cosine distance) |
| Image processing | OpenCV 4, NumPy, SciPy |
| Frontend | Vanilla JavaScript (no build step, no framework) |
| Charts | Chart.js 4 |
| Fonts | Syne, Nunito, IBM Plex Mono |
| Slack | slack-bolt (Socket Mode, Block Kit messages, `/who-is-in` slash command) |

---

## Quick Start

Tested on macOS, Linux, and WSL. Windows native should work but is untested.

### Prerequisites

- Python 3.10 or newer
- A webcam for kiosk use. The dashboard works without one.
- A Slack workspace where you can install an app and get both a bot token (`xoxb-...`) and an app-level token (`xapp-...`).

### Install

```bash
git clone https://github.com/your-org/isel_room.git
cd isel_room
python -m venv .venv
source .venv/bin/activate           # macOS/Linux
# .venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

> The first `pip install` is slow (~3 minutes) because DeepFace pulls in TensorFlow. This is a one-time cost.

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

This drops and recreates the DB with 11 mock members and about 60 days of fake attendance history. Re-run it any time during development to reset.

### Run

```bash
flask --app app run --host 0.0.0.0 --port 5001
```

Open <http://localhost:5001> in a browser. The Check-in screen loads by default. Press `D` to switch to the Dashboard.

> **Production:** use `wsgi.py` with gunicorn. The auto-checkout job is a CLI command (`flask auto-checkout`). Schedule it via cron, not as part of the web process.

---

## Basic Usage

### As a lab member (at the kiosk)

1. Walk up to the camera.
2. Press `Enter` (or click **Scan Face**).
3. Confirm the match with `Enter`. The screen says "Welcome, <name>!" or "See you, <name>!".

If your face is not matched, press `Space` to pick your name from a list.

### As the sensei or admin (on the dashboard)

| Key | Tab |
|---|---|
| `1` | Overview. Stat cards, charts, recent activity. |
| `2` | Attendance. Weekly grid and leaderboards. |
| `3` | Members. Add, edit, delete, re-register (PIN required). |
| `4` | Activity Log. Full audit log with filters (PIN required). |

**Add a new member:** Members tab → Add Member → enter name and role → 3-step face capture wizard. Normal is required. Glasses and Mask are optional. The wizard bursts 3 frames per step for robustness.

**Promote students at year-end:** Members tab → Promote Students → walk through each student in the wizard and pick their new role (M1 → M2, M2 → 卒業 or PhD, and so on). All changes are applied atomically and logged.

### Nightly auto-checkout (cron)

Add this to your crontab to force-close forgotten sessions every night at 22:00:

```cron
0 22 * * *  cd /path/to/isel_room && FLASK_APP="app:create_app" flask auto-checkout
```

If you miss a tick, no big deal. Any session open for more than 24 hours is closed automatically on the user's next check-in.

---

## Configuration

All configuration is via environment variables, loaded from `.env`:

| Variable | Default | Required? | Purpose |
|---|---|---|---|
| `FLASK_SECRET_KEY` | `dev-secret-change-me` | **Yes in prod** | Flask session signing key |
| `ADMIN_PIN` | _(empty)_ | **Yes** | PIN for the admin dashboard |
| `SLACK_BOT_TOKEN` | _(empty)_ | **Yes in prod** | Bot token (`xoxb-...`) for posting + editing the status board |
| `SLACK_APP_TOKEN` | _(empty)_ | **Yes in prod** | App-level token (`xapp-...`) for Socket Mode (slash commands) |
| `SLACK_CHANNEL` | `#a-lab-status` | No | Channel where the daily status board is posted |
| `DATABASE_URL` | `sqlite:///isel_room.db` | No | SQLAlchemy connection string |
| `LOW_CONFIDENCE_THRESHOLD` | `0.40` | No | UI badge cutoff for low-confidence matches (cosmetic only) |
| `DAY_RESET_HOUR` | `22` | No | Documents your lab's closing hour. The cron is the actual reset trigger. |

`ProdConfig` (used by `wsgi.py`) refuses to start if any of `FLASK_SECRET_KEY`, `ADMIN_PIN`, `SLACK_BOT_TOKEN`, or `SLACK_APP_TOKEN` is missing. In dev the Slack tokens are still optional; the integration disables itself with a warning and the rest of the app runs normally.

---

## Slack Setup

The integration does two things:

- **Daily status board.** One Block Kit message per day in the channel you choose (`SLACK_CHANNEL`, default `#a-lab-status`), edited in place via `chat.update` as people come and go. No chat firehose.
- **`/who-is-in` slash command.** Anyone in the workspace can run it for an ephemeral reply (only visible to them) with the current present-list.

Setup, once per Slack workspace:

1. Create a Slack app at <https://api.slack.com/apps>.
2. **OAuth & Permissions** → add bot scope `chat:write` (status board) and `commands` (slash command).
3. **Socket Mode** → enable it. Generate an App-Level Token with the `connections:write` scope. Copy it (`xapp-...`).
4. **Slash Commands** → create `/who-is-in`. With Socket Mode on, no request URL is needed.
5. **Install to Workspace** → copy the bot token (`xoxb-...`).
6. Invite the bot to your status channel: `/invite @YourBotName`.
7. Put both tokens in `.env` as `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN`. Optionally set `SLACK_CHANNEL` if you don't want `#a-lab-status`.
8. Restart the app. You should see `Slack: bot client initialised` and `Slack: Socket Mode listener started` in the console.

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
│   ├── db/                 # SQLAlchemy models + session_scope context manager
│   ├── face_engine.py      # DeepFace ArcFace wrapper
│   ├── integrations/       # Slack status board
│   └── utils.py            # @admin_required, decode_image, ok()/fail() helpers
├── tests/                  # pytest suite
└── ui/
    ├── index.html          # Single-page shell
    ├── css/                # tokens, base, checkin, dashboard
    └── js/                 # core, checkin, dashboard
```

See [ISEL_ROOM_GUIDE.md §3](ISEL_ROOM_GUIDE.md#3-repository-layout) for the annotated tree.

---

## Testing

```bash
python -m pytest
```

Runs the full suite (~19 tests) against an in-memory SQLite. No external services required.

---

## Documentation

For everything beyond getting it running:

- **[ISEL_ROOM_GUIDE.md](ISEL_ROOM_GUIDE.md).** Comprehensive architecture. Every layer explained. Face pipeline deep-dive. Frontend module map. State machines. Testing patterns. Common workflows (recipes). Troubleshooting. Read this on your first day.

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

Other conventions (no `Co-Authored-By` lines, comment policy, naming, file-length guidance) live in [ISEL_ROOM_GUIDE.md §12](ISEL_ROOM_GUIDE.md#12-conventions--house-style).

---

## License

_Internal use, KIT Intelligent Software Engineering Lab. Add a formal LICENSE file before publishing externally._

---

## Acknowledgments

- Built for the **ISEL Lab** at the Kyoto Institute of Technology.
