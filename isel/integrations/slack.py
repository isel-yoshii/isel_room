"""Slack integration: daily status board + /who-is-in slash command via Socket Mode.

Two surfaces:

1. Status board: one message per day in the configured channel, edited in place
   as people come and go (chat.update). Called from /api/toggle and
   auto_checkout_all. Block Kit formatted.

2. /who-is-in slash command: ephemeral reply with the current present-list.
   Delivered via Socket Mode (no public HTTP endpoint needed).

All setup happens in init(), called once from app.py during create_app.
Nothing runs at module import; safe to import without Slack tokens.
"""
from __future__ import annotations
import json
import threading
from datetime import datetime
from pathlib import Path

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError

_app: App | None = None
_socket_handler: SocketModeHandler | None = None
_channel: str | None = None
_STATE_PATH = Path(__file__).resolve().parents[2] / 'slack_state.json'


# ── Initialisation ────────────────────────────────────────────

def init(bot_token: str, app_token: str, channel: str) -> None:
    """Configure the Slack integration. Safe to call once at app startup.

    - With both tokens, registers handlers and starts the Socket Mode listener
      on a daemon thread.
    - With only `bot_token`, status-board posting works but no listener.
    - With neither, nothing initialises and update_status_board() is a no-op.
    """
    global _app, _socket_handler, _channel
    _channel = channel

    if not bot_token:
        print('Slack: SLACK_BOT_TOKEN missing; integration disabled')
        return

    _app = App(token=bot_token)
    _register_handlers(_app)
    print('Slack: bot client initialised')

    if not app_token:
        print('Slack: SLACK_APP_TOKEN missing; Socket Mode disabled (status board still posts)')
        return

    _socket_handler = SocketModeHandler(_app, app_token)
    threading.Thread(
        target=_socket_handler.start,
        daemon=True,
        name='slack-socket-mode',
    ).start()
    print('Slack: Socket Mode listener started')


def _register_handlers(app: App) -> None:
    @app.command('/who-is-in')
    def _who_is_in(ack, respond):
        ack()
        from isel.services.attendance import get_present_users_detailed
        present = get_present_users_detailed()
        respond(
            blocks=_present_blocks(present),
            text=_fallback_text(present),
            response_type='ephemeral',
        )


# ── Block Kit rendering ──────────────────────────────────────

def _present_blocks(present: list[dict]) -> list[dict]:
    """Block Kit JSON for the current present-list. Used by both surfaces."""
    n = len(present)
    icon = '🟢' if n else '⚫'
    header_text = f'{icon} {n} in the lab' if n else f'{icon} Lab is empty'

    blocks: list[dict] = [
        {'type': 'header', 'text': {'type': 'plain_text', 'text': header_text, 'emoji': True}},
    ]
    if present:
        body = '\n'.join(f'• {u["name"]} ({u.get("type") or "?"})' for u in present)
        blocks.append({'type': 'section', 'text': {'type': 'mrkdwn', 'text': body}})
    blocks.append({
        'type': 'context',
        'elements': [{'type': 'mrkdwn', 'text': f'_Updated {datetime.now().strftime("%H:%M")}_'}],
    })
    return blocks


def _fallback_text(present: list[dict]) -> str:
    """Short plain-text fallback used for push notifications and accessibility."""
    n = len(present)
    return f'🟢 {n} in the lab' if n else '⚫ Lab is empty'


# ── Daily status board (write path) ──────────────────────────

def _load_state() -> dict:
    if not _STATE_PATH.exists():
        return {}
    try:
        return json.loads(_STATE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    _STATE_PATH.write_text(json.dumps(state), encoding='utf-8')


def update_status_board() -> None:
    """Refresh the daily status board in the configured channel.

    Edits today's message in place if it exists; otherwise posts a new one.
    Failures are logged and swallowed so check-in never blocks on Slack.
    """
    if not _app or not _channel:
        return
    try:
        from isel.services.attendance import get_present_users_detailed
        present = get_present_users_detailed()
        blocks = _present_blocks(present)
        text   = _fallback_text(present)
        today  = datetime.now().strftime('%Y-%m-%d')
        state  = _load_state()

        same_day = state.get('date') == today and state.get('channel') == _channel
        if same_day and state.get('ts'):
            try:
                _app.client.chat_update(channel=_channel, ts=state['ts'], text=text, blocks=blocks)
                return
            except SlackApiError as e:
                if e.response.get('error') != 'message_not_found':
                    raise
                # Someone deleted today's message; fall through and post fresh.

        resp = _app.client.chat_postMessage(channel=_channel, text=text, blocks=blocks)
        _save_state({'ts': resp['ts'], 'date': today, 'channel': _channel})
    except Exception as e:
        print(f'Slack status board update failed: {e}')
