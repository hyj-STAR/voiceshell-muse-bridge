import base64
import io
import json
import os
import sys
import time
from pathlib import Path

import pytest

SDK = Path(os.environ['MUSE_SDK_LINUX_DIR'])
sys.path.insert(0, str(SDK / 'tests'))
from test_ble_setup import Harness, PROVISION
from test_pairing import hello, client_finished_record
from musegadget.ble_framing import ChunkAssembler, encode_chunks
from server_pairing_relay import StdioTransport, dispatch


def deliver(h, obj):
    for packet in encode_chunks(json.dumps(obj).encode(), 163):
        dispatch({'event': 'write', 'data': base64.b64encode(packet).decode()},
                 h.controller, h.transport)


def wait_until(predicate):
    end = time.monotonic() + 2
    while not predicate():
        assert time.monotonic() < end
        time.sleep(0.01)


def test_stdio_packets_roundtrip_at_small_mtu():
    output = io.StringIO()
    transport = StdioTransport(output)
    dispatch({'event': 'mtu', 'value': 23}, None, transport)
    payload = b'public-test-payload' * 4
    transport.send_packets(encode_chunks(payload, transport.mtu()))
    assembler = ChunkAssembler()
    result = None
    for line in output.getvalue().splitlines():
        event = json.loads(line)
        packet = base64.b64decode(event['data'])
        assert len(packet) <= 20
        result = assembler.feed(packet)
    assert result == payload


def test_official_encrypted_setup_over_relay_dispatch():
    h = Harness()
    h.controller.start()
    try:
        deliver(h, hello())
        wait_until(lambda: len(h.transport.messages) == 1)
        deliver(h, client_finished_record())
        h.mobile.tx_counter = 1
        wait_until(lambda: h.statuses() == ['pairing_confirmed'])
        deliver(h, h.mobile.seal({'action': 'wifi_scan'}))
        wait_until(lambda: any(m.get('type') == 'wifi_scan_result' for m in h.opened()))
        deliver(h, h.mobile.seal(PROVISION))
        h.wait_for_status('auth_ok')
        assert h.completed.is_set()
        assert len(h.saved) == 1
    finally:
        h.controller.stop()


def test_plaintext_provision_not_authorized():
    h = Harness()
    h.controller.start()
    try:
        deliver(h, PROVISION)
        wait_until(lambda: h.transport.messages)
        assert h.transport.messages == ['error_encryption_required']
        assert not h.saved
    finally:
        h.controller.stop()


def test_invalid_base64_rejected():
    with pytest.raises(ValueError):
        dispatch({'event': 'write', 'data': '!!!'}, None, None)


def test_oversize_att_write_rejected():
    with pytest.raises(ValueError):
        dispatch({'event': 'write', 'data': base64.b64encode(b'x' * 513).decode()}, None, None)


def test_mtu_clamped():
    transport = StdioTransport(io.StringIO())
    dispatch({'event': 'mtu', 'value': 9999}, None, transport)
    assert transport.mtu() == 163
    dispatch({'event': 'mtu', 'value': 0}, None, transport)
    assert transport.mtu() == 23
