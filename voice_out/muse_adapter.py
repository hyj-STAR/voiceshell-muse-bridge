"""Opt-in Muse command adapter; no SDK default shell/file commands exposed."""
import json
from pathlib import Path
import urllib.error
import urllib.request
import uuid


COMMAND_SPECS = {
    'voiceshell.output_text': {
        'description': 'Queue text for VoiceShell output. Queued is NOT spoken. No shell access.',
        'required': {'text': {'type': 'string', 'description': 'Text for the user.'}},
        'optional': {'responseId': {'type': 'string', 'description': 'Idempotent ID; reuse on retry.'}},
        'timeout_ms': 10000,
    },
}


class VoiceOutExecutor:
    def __init__(self, key_path, port=18789):
        self.key_path, self.port = Path(key_path), port

    def run(self, command, params, timeout_ms=None):
        if command not in COMMAND_SPECS:
            return {'ok': False, 'error': 'command_not_allowed'}
        if not isinstance(params, dict):
            return {'ok': False, 'error': 'invalid_parameters'}
        try:
            payload = {'text': params.get('text'), 'responseId': params.get('responseId') or 'muse-' + uuid.uuid4().hex}
            request = urllib.request.Request(
                f'http://127.0.0.1:{self.port}/v1/output/text',
                data=json.dumps(payload).encode(),
                headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.key_path.read_text().strip()})
            # Loopback bridge never passes through an environment-configured proxy.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=5) as response:
                return {'ok': True, 'payload': json.load(response)}
        except (OSError, ValueError, urllib.error.URLError):
            return {'ok': False, 'error': 'bridge_unavailable_or_rejected'}


def run_paired_service(key_path, port=18789):
    """Use upstream refresh/backoff with an explicitly restricted capability list.

    Must use a separate, already-paired Linux SDK state directory. Does not
    copy ESP32 credentials or enable an unverified account binding.
    """
    import asyncio
    import signal
    import time
    from musegadget import __version__, config, identity
    from musegadget.link_client import DeviceDescription, LinkSession, Outcome
    from musegadget.service import Service, DEFAULT_NOISE_HOST

    if not config.load_json(config.PAIRING_FILE):
        raise RuntimeError('Muse Linux identity is not paired; adapter not started')

    class RestrictedService(Service):
        async def _session(self, vm, pairing):
            device = DeviceDescription(self.identity.node_id, 'VoiceShell Bridge', __version__, COMMAND_SPECS)
            session = LinkSession(noise_host=pairing.get('noise_host') or DEFAULT_NOISE_HOST,
                vm_id=vm['vm_id'] or vm['vm_name'], vm_auth_token=vm['vm_auth_token'],
                device=device, run_command=self.executor.run)
            self._current = session
            try:
                outcome = await session.run(self._stop)
            except Exception:
                outcome = Outcome.CLOSED
            finally:
                self._current = None
            return outcome, time.monotonic() - (session.registered_at or time.monotonic())

    async def main():
        service = RestrictedService(identity.load_or_create(), VoiceOutExecutor(key_path, port), config.sdk_token())
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_running_loop().add_signal_handler(sig, service.stop)
        await service.run()

    asyncio.run(main())


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--producer-key', required=True)
    parser.add_argument('--port', type=int, default=18789)
    args = parser.parse_args()
    run_paired_service(args.producer_key, args.port)
