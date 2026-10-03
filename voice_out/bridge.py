"""Single-owner experimental Voice Out queue. Loopback only; no shell tools."""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Queue:
    def __init__(self, state):
        state = Path(state)
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(state / 'queue.sqlite3', check_same_thread=False)
        self.lock = threading.Lock()
        self.db.execute('''CREATE TABLE IF NOT EXISTS messages (
            response_id TEXT PRIMARY KEY, digest TEXT NOT NULL, text TEXT,
            status TEXT NOT NULL, created REAL NOT NULL, lease TEXT, leased REAL)''')
        self.db.commit()
        self.keys = {}
        for role in ('producer', 'consumer'):
            path = state / (role + '.key')
            if not path.exists():
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w') as output:
                    output.write(secrets.token_urlsafe(32))
            self.keys[role] = path.read_text().strip()
        if any(len(key) < 32 for key in self.keys.values()):
            raise ValueError('Invalid credentials')
        self.expire()

    def expire(self):
        # Clear content on expiry; retain idempotency metadata for at most a day.
        now = time.time()
        self.db.execute("UPDATE messages SET text=NULL,status='expired' WHERE created<? AND text IS NOT NULL", (now - 1800,))
        self.db.execute('DELETE FROM messages WHERE created<?', (now - 86400,))
        self.db.commit()

    def submit(self, data):
        text, rid = data.get('text'), data.get('responseId')
        if not isinstance(text, str) or not text.strip() or len(text.encode()) > 8192:
            raise ValueError('text must contain 1..8192 UTF-8 bytes')
        if not isinstance(rid, str) or not 1 <= len(rid) <= 80 or not all(c.isascii() and (c.isalnum() or c in '-_') for c in rid):
            raise ValueError('Invalid responseId')
        digest = hashlib.sha256(text.encode()).hexdigest()
        with self.lock:
            self.expire()
            existing = self.db.execute('SELECT digest,status FROM messages WHERE response_id=?', (rid,)).fetchone()
            if existing:
                if existing[0] != digest:
                    return 409, {'error': 'response_id_conflict'}
                return 200, {'responseId': rid, 'status': existing[1], 'duplicate': True}
            count = self.db.execute("SELECT count(*) FROM messages WHERE status IN ('queued','leased')").fetchone()[0]
            if count >= 100:
                return 429, {'error': 'queue_full'}
            self.db.execute('INSERT INTO messages VALUES (?,?,?,?,?,?,?)', (rid, digest, text, 'queued', time.time(), None, None))
            self.db.commit()
        return 202, {'responseId': rid, 'status': 'queued', 'played': False}

    def next(self):
        with self.lock:
            self.expire()
            self.db.execute("UPDATE messages SET status='queued',lease=NULL WHERE status='leased' AND leased<?", (time.time() - 60,))
            row = self.db.execute("SELECT response_id,text FROM messages WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if not row:
                self.db.commit()
                return {'event': None}
            lease = secrets.token_urlsafe(24)
            self.db.execute("UPDATE messages SET status='leased',lease=?,leased=? WHERE response_id=?", (lease, time.time(), row[0]))
            self.db.commit()
            return {'event': {'type': 'voice.output.text', 'responseId': row[0], 'text': row[1], 'lease': lease, 'leaseSeconds': 60}}

    def acknowledge(self, data):
        rid, lease, status = data.get('responseId'), data.get('lease'), data.get('status')
        if not isinstance(rid, str) or not isinstance(lease, str) or status not in ('delivered', 'failed', 'cancelled'):
            raise ValueError('Invalid acknowledgment')
        with self.lock:
            self.expire()
            row = self.db.execute('SELECT lease,status,leased FROM messages WHERE response_id=?', (rid,)).fetchone()
            if not row or row[1] != 'leased' or not hmac.compare_digest(row[0] or '', lease) or row[2] < time.time() - 60:
                return 409, {'error': 'lease_not_active'}
            self.db.execute('UPDATE messages SET status=?,text=NULL,lease=NULL WHERE response_id=?', (status, rid))
            self.db.commit()
        return 200, {'responseId': rid, 'status': status}


def server(state, port=18789):
    queue = Queue(state)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Never log bearer headers or text.

        def reply(self, status, data):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def authorized(self, role):
            expected = 'Bearer ' + queue.keys[role]
            return hmac.compare_digest(self.headers.get('Authorization', '').encode('utf-8'), expected.encode())

        def do_GET(self):
            if self.path == '/health':
                self.reply(200, {'service': 'voiceshell-voice-out', 'version': 1, 'museBinding': 'not_verified', 'audioPlayback': 'not_implemented'})
            elif self.path == '/v1/output/next':
                self.reply(200, queue.next()) if self.authorized('consumer') else self.reply(401, {'error': 'unauthorized'})
            else:
                self.reply(404, {'error': 'not_found'})

        def do_POST(self):
            routes = {'/v1/output/text': ('producer', queue.submit), '/v1/output/ack': ('consumer', queue.acknowledge)}
            route = routes.get(self.path)
            if not route:
                return self.reply(404, {'error': 'not_found'})
            if not self.authorized(route[0]):
                return self.reply(401, {'error': 'unauthorized'})
            try:
                if self.headers.get('Transfer-Encoding'):
                    raise ValueError('Chunked requests are not supported')
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    return self.reply(413, {'error': 'body_too_large'})
                self.connection.settimeout(5)
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError('JSON object required')
                code, result = route[1](data)
                self.reply(code, result)
            except (ValueError, TypeError, TimeoutError):
                self.reply(400, {'error': 'invalid_request'})

    class BoundedServer(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True
        workers = threading.BoundedSemaphore(16)

        def process_request(self, request, client_address):
            if not self.workers.acquire(blocking=False):
                self.shutdown_request(request)
                return
            try:
                super().process_request(request, client_address)
            except Exception:
                self.workers.release()
                raise

        def process_request_thread(self, request, client_address):
            try:
                super().process_request_thread(request, client_address)
            finally:
                self.workers.release()

        def server_close(self):
            super().server_close()
            with queue.lock:
                queue.db.close()

        def get_request(self):
            sock, address = super().get_request()
            sock.settimeout(5)
            return sock, address

    return BoundedServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', required=True)
    parser.add_argument('--port', type=int, default=18789)
    args = parser.parse_args()
    os.umask(0o077)
    server(args.state, args.port).serve_forever()
