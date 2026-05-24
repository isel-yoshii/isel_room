"""Unit tests for the Slack Block Kit renderer.

We intentionally don't mock the Slack API. _present_blocks is a pure function
over a list of dicts and is the only piece of slack.py worth unit-testing.
"""
from __future__ import annotations

from isel.integrations.slack import _present_blocks


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
    """A user dict without a 'type' key falls back to '?'."""
    blocks = _present_blocks([{'name': 'Mystery'}])
    assert '• Mystery (?)' in blocks[1]['text']['text']
