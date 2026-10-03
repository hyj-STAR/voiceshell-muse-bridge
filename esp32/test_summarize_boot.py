import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class BootSummaryTest(unittest.TestCase):
    def summarize(self, text):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "boot.log"
            log.write_text(text, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("summarize_boot.py")), str(log)],
                capture_output=True, text=True, check=True,
            )
        return json.loads(result.stdout), result.stdout

    def test_advertising_is_not_claimed_as_phone_discovery(self):
        status, output = self.summarize(
            "SDK token: mgst_dummy_private_token\n"
            "wifi SSID: private-network\n"
            "Found 8MB PSRAM device\n"
            "advertising as MuseGadget-ABC123\n"
        )
        self.assertTrue(status["bleAdvertisingReported"])
        self.assertTrue(status["psramInitReported"])
        self.assertFalse(status["phoneDiscoveryVerified"])
        self.assertFalse(status["pairingVerified"])
        self.assertNotIn("mgst_", output)
        self.assertNotIn("private-network", output)

    def test_empty_and_panic_logs_do_not_look_healthy(self):
        empty, _ = self.summarize("")
        self.assertFalse(empty["bleAdvertisingReported"])
        self.assertFalse(empty["psramInitReported"])
        panic, _ = self.summarize("rst:0x1\nrst:0x1\nGuru Meditation Error\n")
        self.assertTrue(panic["panicReported"])
        self.assertEqual(panic["resetMessages"], 2)

    def test_heartbeat_does_not_require_capturing_initial_boot(self):
        status, _ = self.summarize("hb t=100s setup=advertising wifi=down ws=down raw=down ble=advertising int=164K/62K dma=156K/62K psram=8160K\n")
        self.assertTrue(status["applicationHeartbeatReported"])
        self.assertTrue(status["bleAdvertisingReported"])
        self.assertEqual(status["psramAvailableKiB"], 8160)
        self.assertFalse(status["psramInitReported"])
        self.assertFalse(status["phoneDiscoveryVerified"])


if __name__ == "__main__":
    unittest.main()
