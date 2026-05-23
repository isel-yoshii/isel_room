from __future__ import annotations
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from slack_bolt import App
from slack_sdk.errors import SlackApiError

load_dotenv()

_app = None
token = os.getenv('SLACK_BOT_TOKEN')
if token:
    _app = App(token=token)
    print('Slack: Bot Client Initialized')
else:
    print('Slack: SLACK_BOT_TOKEN is missing')

_DEFAULT_CHANNEL = '#a-lab-status'
_STATE_PATH = Path(__file__).resolve().parents[2] / 'slack_state.json'


def _load_state() -> dict:
    if not _STATE_PATH.exists():
        return {}
    try:
        return json.loads(_STATE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    _STATE_PATH.write_text(json.dumps(state), encoding='utf-8')


def _render(present_users: list[dict]) -> str:
    n = len(present_users)
    icon = '🟢' if n else '⚫'
    header = f'{icon} *{n} in the lab*' if n else f'{icon} *Lab is empty*'
    lines = [f'• {u["name"]} ({u.get("type") or "?"})' for u in present_users]
    footer = f'_Updated {datetime.now().strftime("%H:%M")}_'
    if lines:
        return '\n'.join([header] + lines + ['', footer])
    return f'{header}\n\n{footer}'


def update_status_board(channel: str = _DEFAULT_CHANNEL) -> None:
    """Refresh the daily Slack status board in place.

    Posts a new message if none exists for today (or if the previous one was deleted).
    Otherwise edits the existing message via chat.update. Safe to call from any
    presence-change path; failures are logged and swallowed.
    """
    if not _app:
        return
    try:
        from isel.services.attendance import get_present_users_detailed
        present = get_present_users_detailed()
        text = _render(present)
        today = datetime.now().strftime('%Y-%m-%d')
        state = _load_state()

        same_day = state.get('date') == today and state.get('channel') == channel
        if same_day and state.get('ts'):
            try:
                _app.client.chat_update(channel=channel, ts=state['ts'], text=text)
                return
            except SlackApiError as e:
                if e.response.get('error') != 'message_not_found':
                    raise
                # fall through and post a fresh message

        resp = _app.client.chat_postMessage(channel=channel, text=text)
        _save_state({'ts': resp['ts'], 'date': today, 'channel': channel})
    except Exception as e:
        print(f'Slack status board update failed: {e}')
