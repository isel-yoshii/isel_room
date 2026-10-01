"""The Wi-Fi presence job: scan the network, then let the presence service
turn what was seen into check-ins and check-outs."""
from __future__ import annotations
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Per-process, like the scheduler's own status. `last_success` going stale is
# the only sign that scanning has stopped — nothing else fails visibly.
_state: dict = {
    'enabled': False, 'interval': None,
    'last_attempt': None, 'last_success': None, 'error': None, 'devices': None,
}


def configure(interval_seconds: int) -> None:
    _state.update(enabled=True, interval=interval_seconds)


def status() -> dict:
    return dict(_state)


def run(interface: str, grace_minutes: int) -> dict:
    from backend.integrations import arp_scan
    from backend.services import presence as presence_svc

    now = datetime.now()
    _state['last_attempt'] = now.isoformat()
    try:
        macs = arp_scan.scan(interface)
        result = presence_svc.report(macs, grace_minutes, now)
    except Exception as exc:
        # A failed scan is NOT treated as "nobody is here": report() is skipped,
        # so nobody's grace period counts down while scanning is broken.
        message = str(exc) if isinstance(exc, arp_scan.ScanError) else repr(exc)
        if message != _state['error']:  # once per distinct failure, not once a minute
            logger.error('Wi-Fi presence scan failed: %s', message, exc_info=not isinstance(exc, arp_scan.ScanError))
        _state['error'] = message
        return status()

    if _state['error']:
        logger.warning('Wi-Fi presence scan recovered.')
    _state.update(last_success=now.isoformat(), error=None, devices=len(macs))

    if result['checked_in'] or result['checked_out']:
        try:
            from backend.integrations.slack import update_status_board
            update_status_board()
        except Exception:
            logger.exception('Slack board refresh after Wi-Fi presence scan failed.')
    return status()
