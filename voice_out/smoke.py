"""Run an explicit synthetic message through the deployed loopback queue.

Only fixed test text is used; keys and message payloads are never printed.
"""
import json
from pathlib import Path
import urllib.request
import uuid
from muse_adapter import VoiceOutExecutor


def main(state):
    def request(path, role=None, body=None):
        headers = {'Content-Type': 'application/json'}
        if role:
            headers['Authorization'] = 'Bearer ' + (Path(state) / (role + '.key')).read_text().strip()
        req = urllib.request.Request('http://127.0.0.1:18789' + path,
            headers=headers, data=None if body is None else json.dumps(body).encode())
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=5) as response:
            return json.load(response)

    rid = 'smoke-' + uuid.uuid4().hex
    status = request('/health')
    result = VoiceOutExecutor(Path(state) / 'producer.key').run('voiceshell.output_text',
        {'text': 'VoiceShell synthetic bridge test', 'responseId': rid})
    assert result['ok']
    submitted = result['payload']
    event = request('/v1/output/next', 'consumer')['event']
    if not event or event['responseId'] != rid:
        raise RuntimeError('Unexpected queue item; stop without acknowledging another message')
    acknowledged = request('/v1/output/ack', 'consumer', {**event, 'status': 'delivered'})
    assert submitted['status'] == 'queued' and acknowledged['status'] == 'delivered'
    print(json.dumps({'service': status['service'], 'queueRoundTrip': 'passed',
        'museAccountBinding': 'not_verified', 'realAudioPlayback': 'not_tested'}))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', required=True)
    main(parser.parse_args().state)
