"""Unit tests for the Slack Block Kit renderers — pure functions over dicts, so
nothing here mocks the Slack API."""
from __future__ import annotations

from backend.integrations.slack import _present_blocks, _points_blocks


def test_present_blocks_empty_list():
    blocks = _present_blocks([])
    # header + context (no section when empty)
    assert [b['type'] for b in blocks] == ['header', 'context']
    assert 'Lab is empty' in blocks[0]['text']['text']
    assert '⚫' in blocks[0]['text']['text']


def test_present_blocks_single_user():
    blocks = _present_blocks([{'name': 'Naimi', 'type': 'M1'}])
    assert [b['type'] for b in blocks] == ['header', 'section', 'context']
    assert '1 in the lab' in blocks[0]['text']['text']
    assert '🟢' in blocks[0]['text']['text']
    assert '• Naimi (M1)' in blocks[1]['text']['text']


def test_present_blocks_multiple_users():
    present = [
        {'name': 'Inoue',    'type': 'M2'},
        {'name': 'Naimi',    'type': 'M1'},
        {'name': 'Yamamoto', 'type': 'B4'},
    ]
    blocks = _present_blocks(present)
    assert '3 in the lab' in blocks[0]['text']['text']
    body = blocks[1]['text']['text']
    assert '• Inoue (M2)' in body
    assert '• Naimi (M1)' in body
    assert '• Yamamoto (B4)' in body
    # Footer is a context block with an "Updated HH:MM" string.
    assert blocks[2]['type'] == 'context'
    assert 'Updated' in blocks[2]['elements'][0]['text']


def test_present_blocks_handles_missing_type():
    blocks = _present_blocks([{'name': 'Mystery'}])
    assert '• Mystery (?)' in blocks[1]['text']['text']


def test_points_blocks_empty_leaderboard():
    blocks = _points_blocks([], 2026, 5)
    assert [b['type'] for b in blocks] == ['header', 'section', 'context']
    assert 'May 2026' in blocks[0]['text']['text']
    assert 'Top' not in blocks[0]['text']['text']     # no "Top 0"
    assert 'No activity' in blocks[1]['text']['text']


def test_points_blocks_top_three_get_medals():
    rows = [
        {'name': 'Naimi', 'type': 'M1', 'points': 18},
        {'name': 'Inoue', 'type': 'M2', 'points': 16},
        {'name': 'Yoshii', 'type': 'M1', 'points': 14},
    ]
    blocks = _points_blocks(rows, 2026, 5)
    assert '🏆 Top 3 — May 2026' in blocks[0]['text']['text']
    body = blocks[1]['text']['text']
    assert '🥇 Naimi (M1) — 18 days' in body
    assert '🥈 Inoue (M2) — 16 days' in body
    assert '🥉 Yoshii (M1) — 14 days' in body


def test_points_blocks_after_third_uses_numeric_rank():
    rows = [
        {'name': f'User{i}', 'type': 'M1', 'points': 10 - i}
        for i in range(5)
    ]
    blocks = _points_blocks(rows, 2026, 5)
    body = blocks[1]['text']['text']
    assert '🥇 User0' in body
    assert '🥈 User1' in body
    assert '🥉 User2' in body
    assert '4. User3' in body
    assert '5. User4' in body


def test_points_blocks_single_day_uses_singular_suffix():
    blocks = _points_blocks([{'name': 'Lone', 'type': 'B4', 'points': 1}], 2026, 5)
    body = blocks[1]['text']['text']
    assert '— 1 day' in body
    assert '— 1 days' not in body
