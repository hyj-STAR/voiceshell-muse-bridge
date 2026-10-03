"""Carry encrypted setup over two SSH stdio processes; no inbound listener.

Use a local SSH config for the Windows host and isolated Linux backend host.
Secrets stay server-side; do not pass a token in command-line arguments.
"""
import argparse
import json
import subprocess
import threading
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--windows-host', required=True)
    parser.add_argument('--windows-key')
    parser.add_argument('--windows-command', required=True)
    parser.add_argument('--backend-host', required=True)
    parser.add_argument('--backend-command', required=True)
    args = parser.parse_args()
    processes = []
    ended = threading.Event()
    complete = threading.Event()

    def start(host, command, key=None):
        if host.startswith('-') or any(c.isspace() for c in host):
            raise ValueError('Invalid SSH host')
        argv = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8']
        if key:
            argv += ['-i', key, '-o', 'IdentitiesOnly=yes']
        process = subprocess.Popen(argv + [host, command], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        processes.append(process)
        return process

    def forward(source, target, allowed):
        try:
            while not ended.is_set():
                line = source.stdout.readline(32769)
                if not line:
                    break
                if len(line) > 32768:
                    raise ValueError('Oversized relay event')
                event = json.loads(line)
                kind = event.get('event')
                if kind not in allowed:
                    raise ValueError('Unexpected relay event')
                target.stdin.write(line)
                target.stdin.flush()
                if kind == 'ready':
                    print('BACKEND_READY', flush=True)
                if kind == 'complete':
                    complete.set()
                    print('BACKEND_AUTHORIZATION_SAVED_NO_CONTROL_EXECUTOR', flush=True)
        except (ValueError, KeyError, BrokenPipeError, OSError):
            print('RELAY_TRANSPORT_STOPPED', flush=True)
        finally:
            ended.set()

    def drain(process, show=False):
        while True:
            line = process.stderr.readline(4097)
            if not line:
                return
            # Only fixed diagnostic labels from our Windows executable are shown.
            if show and line.startswith((b'GATT_ADVERTISEMENT:', b'MANUFACTURER_ADVERTISEMENT:',
                                         b'PHONE_SUBSCRIBED', b'PHONE_WRITE', b'EXPERIMENT_FAILED:',
                                         b'PERIPHERAL_ROLE_OR_RADIO_UNAVAILABLE')):
                print(line.decode('utf-8', 'replace').strip(), flush=True)

    try:
        backend = start(args.backend_host, args.backend_command)
        windows = start(args.windows_host, args.windows_command, args.windows_key)
        for process, show in ((backend, False), (windows, True)):
            threading.Thread(target=drain, args=(process, show), daemon=True).start()
        threading.Thread(target=forward, args=(backend, windows,
            {'ready', 'packet', 'disconnect', 'complete'}), daemon=True).start()
        threading.Thread(target=forward, args=(windows, backend,
            {'write', 'mtu', 'disconnect'}), daemon=True).start()
        deadline = time.monotonic() + 600
        while not ended.wait(0.2) and time.monotonic() < deadline:
            pass
        if complete.is_set():
            # Windows drains final status briefly before stopping GATT.
            time.sleep(2)
        print('RELAY_CLOSED_PAIRED=' + str(complete.is_set()).lower(), flush=True)
    finally:
        ended.set()
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    main()
