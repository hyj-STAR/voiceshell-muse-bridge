"""Summarize the upstream monitor's private log without echoing credentials."""

import argparse
import json
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    data = args.log.read_bytes()
    text = data.decode("utf-8", errors="replace")
    names = re.findall(r"advertising as (MuseGadget-[A-Za-z0-9_-]+)", text)
    heartbeat = bool(re.search(r"hb t=\d+s ", text))
    psram = re.findall(r"psram=(\d+)K", text)
    print(json.dumps({
        "capturedBytes": len(data),
        "applicationHeartbeatReported": heartbeat,
        "bleAdvertisingReported": bool(names) or "BLE advertising; press the button" in text or bool(re.search(r"\bble=advertising\b", text)),
        "advertisedName": names[-1] if names else None,
        "psramInitReported": bool(re.search(r"Found \d+MB PSRAM|Adding pool of .* PSRAM", text)),
        "psramAvailableKiB": int(psram[-1]) if psram else None,
        "panicReported": bool(re.search(r"Guru Meditation|panic'ed|abort\(\) was called", text)),
        "resetMessages": len(re.findall(r"rst:0x", text)),
        "phoneDiscoveryVerified": False,
        "pairingVerified": False,
    }))


if __name__ == "__main__":
    main()
