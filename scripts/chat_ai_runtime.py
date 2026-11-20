"""Run the optional loopback chat backend alongside the installed game server."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


CONFIG = '_setup/chat-ai/config.json'
KEY = '_setup/chat-ai/api.local.key'
ADDRESS = '127.0.0.1'
ROUTE = '/v1/chat/completions'
LIMIT = 256 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def serve_api(root, config):
    path = root / KEY
    token = ''
    if path.exists():
        if path.is_symlink() or path.stat().st_mode & 0o077:
            raise ValueError('The API key file must be private.')
        token = path.read_text(encoding='ascii').strip()
    upstream = build_opener(NoRedirect())

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send_json(self, status, payload):
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def failure(self, status):
            self.send_json(status, b'{"error":{"message":"Chat AI request failed"}}')

        def do_GET(self):
            if self.path == '/health':
                self.send_json(200, b'{"status":"ok"}')
            else:
                self.failure(404)

        def do_POST(self):
            if self.path != ROUTE:
                self.failure(404)
                return
            if self.headers.get('Origin') or self.headers.get_content_type() != 'application/json':
                self.failure(415)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= LIMIT:
                    raise ValueError
                self.connection.settimeout(4)
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict) or not isinstance(payload.get('messages'), list):
                    raise ValueError
            except (ValueError, OSError):
                self.failure(400)
                return
            payload['model'] = config['model']
            headers = {'Content-Type': 'application/json'}
            if token:
                headers['Authorization'] = 'Bearer ' + token
            request = Request(config['endpoint'], json.dumps(payload).encode(), headers)
            try:
                with upstream.open(request, timeout=14) as reply:
                    answer = reply.read(LIMIT + 1)
                if len(answer) > LIMIT or not isinstance(json.loads(answer), dict):
                    raise ValueError
            except HTTPError as error:
                print(f'Chat AI provider HTTP {error.code}.', file=sys.stderr, flush=True)
                self.failure(502)
                return
            except (OSError, URLError, ValueError):
                print('Chat AI provider unavailable or returned invalid JSON.', file=sys.stderr, flush=True)
                self.failure(502)
                return
            self.send_json(200, answer)

    with ThreadingHTTPServer((ADDRESS, config['port']), Handler) as proxy:
        proxy.serve_forever()


def backend_command(root, config):
    if config['mode'] == 'api':
        return [sys.executable, __file__, '--proxy', str(root)]
    work = root / '_setup/chat-ai'
    return ['nice', '-n', '10', str(work / 'llama/llama-server'),
            '--model', str(work / 'model.gguf'), '--alias', 'yapb-local',
            '--host', ADDRESS, '--port', str(config['port']), '--threads', '2',
            '--threads-batch', '2', '--ctx-size', '2048', '--parallel', '1',
            '--n-gpu-layers', '0', '--cors-origins', 'localhost']


def wait_ready(backend, port):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if backend.poll() is not None:
            break
        try:
            with urlopen(f'http://{ADDRESS}:{port}/health', timeout=1) as response:
                if json.load(response).get('status') == 'ok' and backend.poll() is None:
                    return
        except (OSError, ValueError):
            pass
        time.sleep(.25)
    raise ValueError('Chat AI backend failed to start. See _setup/chat-ai/backend.log.')


def stop(process):
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run(root, config, command):
    with socket.socket() as port:
        port.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            port.bind((ADDRESS, config['port']))
        except OSError:
            raise ValueError(f"Chat AI loopback port {config['port']} is already in use.") from None
    env = os.environ.copy()
    env.pop('LD_LIBRARY_PATH', None)
    backend = game = None

    def shutdown(number, frame):
        raise SystemExit(128 + number)

    for number in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(number, shutdown)
    try:
        with (root / '_setup/chat-ai/backend.log').open('ab') as log:
            backend = subprocess.Popen(backend_command(root, config), cwd=root, env=env,
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       start_new_session=True)
        wait_ready(backend, config['port'])
        game = subprocess.Popen(command, cwd=root)
        code = game.wait()
        return code if code >= 0 else 128 - code
    finally:
        for number in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            signal.signal(number, signal.SIG_IGN)
        stop(game)
        stop(backend)


def wrap(root, command):
    """Wrap the validated HLDS command only when the installation has Chat AI."""
    if not (root / CONFIG).is_file():
        return command
    helper = root / '_setup/tools/chat_ai_runtime.py'
    return [sys.executable, str(helper), str(root), *command]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy', action='store_true')
    parser.add_argument('root', type=Path)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = args.root.resolve()
    os.umask(0o077)
    config = json.loads((root / CONFIG).read_text(encoding='ascii'))
    if args.proxy:
        serve_api(root, config)
        return 0
    return run(root, config, args.command)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f'Chat AI startup stopped: {error}', file=sys.stderr)
        sys.exit(1)
