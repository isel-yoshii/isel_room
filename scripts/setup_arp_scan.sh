#!/usr/bin/env bash
# One-time setup on the lab PC (Ubuntu): install arp-scan and let it open raw
# sockets without root, so ISELROOM can scan the Wi-Fi as an ordinary user.
#
#   sudo scripts/setup_arp_scan.sh
#
# RE-RUN THIS after any apt upgrade that replaces arp-scan: the capability is
# stored on the binary and is lost when the file is replaced. The symptom is the
# dashboard showing "Wi-Fi Scan Failing" with a permission error.
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Linux only. On macOS, for development: sudo chown \"\$USER\" /dev/bpf*  (resets on reboot)" >&2
  exit 1
fi
if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo." >&2
  exit 1
fi

command -v arp-scan >/dev/null || apt-get install -y arp-scan
command -v setcap   >/dev/null || apt-get install -y libcap2-bin

bin="$(readlink -f "$(command -v arp-scan)")"
setcap cap_net_raw+ep "$bin"
getcap "$bin"
echo "Done. Check as a normal user: arp-scan --localnet"
