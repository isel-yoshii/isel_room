"""Thin wrapper around the `arp-scan` binary: which MAC addresses are on the
lab network right now.

arp-scan needs raw-socket access. scripts/setup_arp_scan.sh grants it to the
binary once, so the web app itself never runs as root.
"""
from __future__ import annotations
import re
import subprocess

_MAC_RE = re.compile(r'\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b', re.IGNORECASE)


class ScanError(RuntimeError):
    pass


def scan(interface: str = '') -> list[str]:
    # Retries matter: a phone in power-save often misses the first ARP request.
    cmd = ['arp-scan', '--localnet', '--retry=3']
    if interface:
        cmd.append(f'--interface={interface}')
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    except FileNotFoundError:
        raise ScanError('arp-scan is not installed (run scripts/setup_arp_scan.sh)')
    except subprocess.TimeoutExpired:
        raise ScanError('arp-scan timed out')
    if out.returncode != 0:
        detail = ' '.join(out.stderr.split()) or f'exit code {out.returncode}'
        raise ScanError(f'arp-scan failed: {detail}')
    return sorted({m.lower() for m in _MAC_RE.findall(out.stdout)})
