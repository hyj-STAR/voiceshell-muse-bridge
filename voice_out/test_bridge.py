import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from bridge import Queue, server
from muse_adapter import COMMAND_SPECS, VoiceOutExecutor


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.queue = Queue(self.temp.name)

    def tearDown(self):
        self.queue.db.close()
        self.temp.cleanup()

    def test_idempotency_and_conflict(self):
        self.assertEqual(self.queue.submit({'responseId': 'a', 'text': 'hello'})[0], 202)
        self.assertEqual(self.queue.submit({'responseId': 'a', 'text': 'hello'})[0], 200)
        self.assertEqual(self.queue.submit({'responseId': 'a', 'text': 'changed'})[0], 409)

    def test_delivery_not_playback(self):
        self.queue.submit({'responseId': 'a', 'text': '你好'})
        event = self.queue.next()['event']
        self.assertIsNone(self.queue.next()['event'])
        self.assertEqual(self.queue.acknowledge({'responseId': 'a', 'lease': 'wrong', 'status': 'delivered'})[0], 409)
        self.assertEqual(self.queue.acknowledge({**event, 'status': 'delivered'})[0], 200)
        self.assertIsNone(self.queue.db.execute('SELECT text FROM messages').fetchone()[0])

    def test_expired_lease_requeues(self):
        self.queue.submit({'responseId': 'a', 'text': 'hello'})
        first = self.queue.next()['event']
        self.queue.db.execute('UPDATE messages SET leased=0')
        self.queue.db.commit()
        self.assertEqual(self.queue.acknowledge({**first, 'status': 'delivered'})[0], 409)
        self.assertNotEqual(self.queue.next()['event']['lease'], first['lease'])

    def test_expiry_and_queue_limit(self):
        for i in range(100):
            self.queue.submit({'responseId': str(i), 'text': 'hello'})
        self.assertEqual(self.queue.submit({'responseId': 'full', 'text': 'hello'})[0], 429)
        self.queue.db.execute('UPDATE messages SET created=0')
        self.queue.expire()
        self.assertIsNone(self.queue.next()['event'])

    def test_invalid_input(self):
        for text, rid in [('', 'a'), ('x' * 8193, 'a'), ('hello', '../a'), ('hi', 1)]:
            with self.assertRaises(ValueError):
                self.queue.submit({'text': text, 'responseId': rid})


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = server(self.temp.name, 0)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, role=None, data=None):
        headers = {}
        if role:
            headers['Authorization'] = 'Bearer ' + (Path(self.temp.name) / (role + '.key')).read_text()
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}',
            data=None if data is None else json.dumps(data).encode(), headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as response:
            return response.code, json.load(response)

    def test_roles_and_no_auth(self):
        self.assertEqual(self.request('/v1/output/next')[0], 401)
        self.assertEqual(self.request('/v1/output/next', 'producer')[0], 401)
        self.assertEqual(self.request('/v1/output/text', 'consumer', {'text': 'hello', 'responseId': 'a'})[0], 401)
        self.assertEqual(self.request('/health')[1]['audioPlayback'], 'not_implemented')

    def test_muse_command_to_consumer(self):
        executor = VoiceOutExecutor(Path(self.temp.name) / 'producer.key', self.port)
        self.assertEqual(list(COMMAND_SPECS), ['voiceshell.output_text'])
        self.assertFalse(executor.run('system.run', {'command': 'anything'})['ok'])
        result = executor.run('voiceshell.output_text', {'text': 'VoiceShell test', 'responseId': 'test-1'})
        self.assertEqual(result['payload']['status'], 'queued')
        self.assertFalse(result['payload']['played'])
        event = self.request('/v1/output/next', 'consumer')[1]['event']
        self.assertEqual(event['text'], 'VoiceShell test')
        self.assertEqual(self.request('/v1/output/ack', 'consumer', {**event, 'status': 'delivered'})[0], 200)

    def test_no_arbitrary_routes_or_nonobject(self):
        self.assertEqual(self.request('/v1/shell', 'producer', {})[0], 404)
        self.assertEqual(self.request('/v1/output/text', 'producer', [1])[0], 400)


if __name__ == '__main__':
    unittest.main()
