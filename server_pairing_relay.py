"""Experimental SSH stdio transport for official Muse encrypted BLE setup.

No control executor, listener port, token logging or remote shell API.
"""
import base64
import json
import logging
import os
import sys
import threading
import time

from musegadget import __version__, config, identity, network
from musegadget.ble_setup import SetupController
from musegadget.cli import _verify_and_save
from musegadget.pairing import PairingSession

MAX_LINE = 32768


class StdioTransport:
    def __init__(self, output):
        self.output = output
        self.lock = threading.Lock()
        self.current_mtu = 163

    def emit(self, event):
        with self.lock:
            self.output.write(json.dumps(event, separators=(',', ':')) + '\n')
            self.output.flush()

    def mtu(self):
        return self.current_mtu

    def send_packets(self, packets):
        for i, packet in enumerate(packets):
            if i:
                time.sleep(0.05)
            self.emit({'event': 'packet', 'data': base64.b64encode(packet).decode()})

    def disconnect(self, delay):
        self.emit({'event': 'disconnect', 'delay': delay})


def dispatch(event, controller, transport):
    kind = event.get('event')
    if kind == 'write':
        packet = base64.b64decode(event['data'], validate=True)
        if len(packet) > 512:
            raise ValueError('ATT packet too large')
        controller.on_write(packet)
    elif kind == 'mtu':
        transport.current_mtu = max(23, min(int(event['value']), 163))
    elif kind == 'disconnect':
        controller.on_disconnect()
    else:
        raise ValueError('Unknown relay event')


def main():
    # Keep logs metadata-only. Debug payload logging is never enabled.
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    if config.load_json(config.PAIRING_FILE):
        print('ALREADY_PAIRED: refusing to overwrite authorization', file=sys.stderr)
        return 2
    sdk = config.sdk_token()
    if not sdk:
        print('SDK_TOKEN_MISSING', file=sys.stderr)
        return 2
    ident = identity.load_or_create()
    transport = StdioTransport(sys.stdout)
    pairing = PairingSession(node_id=ident.node_id, device_id=ident.device_id,
                             mac=ident.mac, firmware_version=__version__, sdk_token=sdk)
    controller = SetupController(
        pairing=pairing, identity=ident, version=__version__, transport=transport,
        network=network, provision=_verify_and_save,
        on_complete=lambda: transport.emit({'event': 'complete'}))
    controller.start()
    transport.emit({'event': 'ready', 'name': ident.ble_name, 'node': ident.node_id})
    try:
        while True:
            line = sys.stdin.buffer.readline(MAX_LINE + 1)
            if not line:
                break
            if len(line) > MAX_LINE:
                raise ValueError('Relay message too large')
            dispatch(json.loads(line), controller, transport)
    except (ValueError, KeyError, TypeError):
        print('INVALID_RELAY_MESSAGE', file=sys.stderr)
        return 2
    finally:
        controller.stop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
