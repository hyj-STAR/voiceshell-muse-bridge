"""Minimal USB -> paired Muse test. Does not reset the board or retry posts."""
import argparse
import base64
import json
import time
import uuid


def events(body):
    if not isinstance(body, dict):
        raise ValueError('Invalid history response')
    result = body.get('result', body)
    rows = result.get('chat_events', [])
    if not isinstance(rows, list):
        raise ValueError('Invalid history events')
    return rows


class Client:
    def __init__(self, port):
        import serial
        self.port = serial.Serial(port=None, baudrate=115200, timeout=.2)
        self.port.dtr = False
        self.port.rts = False
        self.port.port = port
        self.port.open()
        self.pending = b''

    def request(self, command, timeout=100):
        if '\n' in command or '\r' in command or '\0' in command or len(command.encode()) >= 2048:
            raise ValueError('Command must be a single USB line below 2048 bytes')
        self.port.write((command + '\n').encode())
        self.port.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.pending += self.port.read(4096)
            if len(self.pending) > 65536:
                raise RuntimeError('Oversized console response')
            while b'\n' in self.pending:
                raw, self.pending = self.pending.split(b'\n', 1)
                line = raw.decode('utf-8', 'replace')
                if '@vs_error ' in line:
                    raise RuntimeError(line.split('@vs_error ', 1)[1])
                for marker in ('@vs_status ', '@vs_reply '):
                    if marker not in line:
                        continue
                    value = json.loads(line.split(marker, 1)[1])
                    if marker == '@vs_status ':
                        return value
                    if not 200 <= value['status'] < 300:
                        raise RuntimeError('Muse HTTP status ' + str(value['status']))
                    return json.loads(base64.b64decode(value['body_b64'], validate=True))
        raise TimeoutError('No USB response; delivery may be unknown. POST not retried.')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', default='COM7')
    p.add_argument('--status', action='store_true')
    p.add_argument('--message')
    p.add_argument('--send-only', action='store_true', help='Send once without requesting chat history; view reply in Muse')
    p.add_argument('--tool-reply', action='store_true', help='Request correlated text back through the advertised device tool')
    a = p.parse_args()
    if a.send_only and a.tool_reply:
        p.error('--send-only and --tool-reply are mutually exclusive')
    if not a.status and not a.message:
        p.error('--status or --message required')
    c = Client(a.port)
    try:
        state = c.request('>status', timeout=10)
        print(json.dumps({'phase': 'status', **state}), flush=True)
        if a.status:
            return
        if not state.get('connected'):
            raise RuntimeError('Muse connection is not ready')
        correlation = str(uuid.uuid4()) if a.tool_reply else None
        message = a.message
        if correlation:
            c.request('>expect=' + correlation)
            message += ' ' + ('Reply using this device\'s voiceshell.reply tool with correlation "' + correlation +
                '" and your answer in text (under 1024 UTF-8 bytes). Do not use any other tools. This returns your answer to the requesting VoiceShell terminal.')
        before = [] if a.send_only or a.tool_reply else events(c.request('>history=latest'))
        after = max((int(row['seq']) for row in before), default=0)
        ack = c.request('>chat=' + message)
        result = ack.get('result', ack)
        message_id = result.get('message_id')
        if not message_id:
            raise RuntimeError('POST returned without message ID; not retried')
        print(json.dumps({'phase': 'sent', 'messageId': message_id}), flush=True)
        if a.send_only:
            return
        if correlation:
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                reply = c.request('>reply', timeout=10)
                if reply.get('correlation') == correlation and reply.get('text'):
                    print(json.dumps({'phase':'reply','transport':'device-tool','text':reply['text']}, ensure_ascii=True), flush=True)
                    return
                time.sleep(2)
            raise TimeoutError('Message sent; no correlated device-tool reply within 120 seconds')
        deadline = time.monotonic() + 120
        after_own = False
        while time.monotonic() < deadline:
            rows = events(c.request('>history=' + str(after)))
            advance = False
            for row in rows:
                seq = int(row['seq'])
                if seq <= after:
                    continue
                event = row.get('event_name')
                if event == 'message.user':
                    after_own = row.get('message_id') == message_id
                reply_to = row.get('reply_to_message_id')
                matches = reply_to == message_id if reply_to else after_own
                if event == 'message.assistant' and matches:
                    if not row.get('display_text_ready'):
                        break
                    text = row.get('display_text')
                    if text:
                        print(json.dumps({'phase': 'reply', 'text': text}, ensure_ascii=True), flush=True)
                        return
                after = seq
                advance = True
            if not advance:
                time.sleep(2)
        raise TimeoutError('Message sent; no correlated completed reply within 120 seconds')
    finally:
        c.port.close()


if __name__ == '__main__':
    main()
