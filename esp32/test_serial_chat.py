import base64
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

spec=importlib.util.spec_from_file_location('bridge',Path(__file__).with_name('serial_chat.py'))
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)

class Port:
    def __init__(self, data): self.data=data;self.writes=[]
    def write(self,data): self.writes.append(data)
    def flush(self): pass
    def read(self,n):
        result,self.data=self.data[:11],self.data[11:]
        return result

class Tests(unittest.TestCase):
    def client(self,data):
        c=bridge.Client.__new__(bridge.Client);c.port=Port(data);c.pending=b'';return c
    def test_status_fragmented_and_noise(self):
        c=self.client(b'boot log\n@vs_status {"chat":true,"connected":true}\n')
        self.assertTrue(c.request('>status',1)['connected'])
        self.assertEqual(c.port.writes,[b'>status\n'])
    def test_unicode_reply(self):
        body=json.dumps({'text':'VoiceShell 已接入'},ensure_ascii=False).encode()
        wire=json.dumps({'status':200,'body_b64':base64.b64encode(body).decode()}).encode()
        c=self.client(b'@vs_reply '+wire+b'\n')
        self.assertEqual(c.request('>history=1',1)['text'],'VoiceShell 已接入')
    def test_http_failure_no_retry(self):
        c=self.client(b'@vs_reply {"status":403,"body_b64":""}\n')
        with self.assertRaises(RuntimeError):c.request('>chat=test',1)
        self.assertEqual(len(c.port.writes),1)
    def test_console_error_no_retry(self):
        c=self.client(b'@vs_error offline\n')
        with self.assertRaises(RuntimeError):c.request('>chat=test',1)
        self.assertEqual(len(c.port.writes),1)
    def test_line_injection_blocked(self):
        for text in ('>chat=a\n>status','>chat=a\r','>chat=a\0','>chat='+'中'*700):
            c=self.client(b'')
            with self.assertRaises(ValueError):c.request(text,0)
            self.assertFalse(c.port.writes)
    def test_timeout_does_not_retry(self):
        c=self.client(b'')
        with self.assertRaises(TimeoutError):c.request('>chat=test',0)
        self.assertEqual(len(c.port.writes),1)
    def test_nested_history(self):
        self.assertEqual(bridge.events({'result':{'chat_events':[{'seq':2}]}}),[{'seq':2}])
    def test_history_shape_rejected(self):
        with self.assertRaises(ValueError):bridge.events({'chat_events':'wrong'})
    def test_send_only_skips_history_and_posts_once(self):
        client=Mock()
        client.request.side_effect=[{'connected':True},{'message_id':'test-id'}]
        with patch.object(bridge,'Client',return_value=client), patch('sys.argv',['serial_chat.py','--send-only','--message','test']), patch('builtins.print'):
            bridge.main()
        self.assertEqual([c.args[0] for c in client.request.call_args_list],['>status','>chat=test'])
        client.port.close.assert_called_once()
    def test_tool_reply_correlates_without_history(self):
        client=Mock()
        client.request.side_effect=[{'connected':True},{'waiting':True},{'message_id':'test-id'},
                                    {'correlation':'wrong','text':'ignore'}, {'correlation':'test-correlation','text':'收到'}]
        with patch.object(bridge,'Client',return_value=client), patch.object(bridge.uuid,'uuid4',return_value='test-correlation'), patch.object(bridge.time,'sleep'), patch('sys.argv',['serial_chat.py','--tool-reply','--message','test']), patch('builtins.print') as output:
            bridge.main()
        commands=[c.args[0] for c in client.request.call_args_list]
        self.assertFalse(any(c.startswith('>history') for c in commands))
        self.assertEqual(sum(c.startswith('>chat=') for c in commands),1)
        self.assertIn('voiceshell.reply',commands[2])
        self.assertEqual(json.loads(output.call_args.args[0])['text'],'收到')

if __name__=='__main__':unittest.main()
