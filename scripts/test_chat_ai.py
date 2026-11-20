from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import chat_ai_runtime as runtime
import install_cs16_linux as installer
from settings import DEFAULTS, get_settings


class ChatAITests(unittest.TestCase):
    def test_mode_selects_only_required_components(self):
        optional = {'easyhttp', 'llama', 'model'}
        self.assertFalse(optional & installer.selected_components(DEFAULTS).keys())
        self.assertEqual(optional & installer.selected_components({'ChatAIMode': 'api'}).keys(), {'easyhttp'})
        self.assertEqual(optional & installer.selected_components({'ChatAIMode': 'local'}).keys(), optional)

    def test_api_settings_and_key_are_separate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings_path = root / 'private.json'
            settings = dict(AdminSteamID='STEAM_0:1:42', ChatAIMode='api',
                            ChatAIEndpoint='https://example.com/v1/chat/completions', ChatAIModel='model')
            settings_path.write_text(json.dumps(settings))
            result = get_settings(settings_path)
            key_path = root / 'key'
            token = 'test-' + 'a' * 160
            key_path.write_text(token + '\n')
            self.assertEqual(installer.read_api_key(result, key_path), token)
            self.assertNotIn(token, json.dumps(result))
            with self.assertRaisesRegex(ValueError, 'HTTPS'):
                installer.read_api_key(dict(result, ChatAIEndpoint='http://example.com/v1/chat/completions'), key_path)
            with self.assertRaises(ValueError):
                installer.read_api_key(DEFAULTS, key_path)
            settings.pop('ChatAIModel')
            settings_path.write_text(json.dumps(settings))
            with self.assertRaisesRegex(ValueError, 'ChatAIModel'):
                get_settings(settings_path)

    @unittest.skipUnless(sys.platform == 'linux', 'Requires the native Linux runtime and loopback')
    def test_proxy_authentication_model_and_error(self):
        seen = []

        class Provider(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                seen.append((self.headers['Authorization'], data))
                if len(seen) == 2:
                    self.send_error(503, 'private upstream diagnostics')
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"choices":[{"message":{"content":"Push B together."}}]}')

        with tempfile.TemporaryDirectory() as temp, HTTPServer(('127.0.0.1', 0), Provider) as provider:
            thread = threading.Thread(target=provider.serve_forever, daemon=True)
            thread.start()
            root = Path(temp)
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            cfg = root / runtime.CONFIG
            cfg.parent.mkdir(parents=True)
            cfg.write_text(json.dumps(dict(mode='api', port=port, model='expected-provider-model',
                                           endpoint=f'http://127.0.0.1:{provider.server_port}/chat')))
            key = root / runtime.KEY
            token = 'test-' + 'a' * 160
            key.write_text(token)
            key.chmod(0o600)
            process = subprocess.Popen([sys.executable, runtime.__file__, '--proxy', str(root)],
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
            try:
                runtime.wait_ready(process, port)
                payload = {'model': 'local-alias', 'messages': [{'role': 'user', 'content': 'Where to?'}]}
                request = Request(f'http://127.0.0.1:{port}{runtime.ROUTE}',
                                  json.dumps(payload).encode(), {'Content-Type': 'application/json'})
                with urlopen(request, timeout=5) as reply:
                    self.assertIn(b'Push B together.', reply.read())
                self.assertEqual(seen[0], ('Bearer ' + token, dict(payload, model='expected-provider-model')))
                with self.assertRaises(HTTPError) as error:
                    urlopen(request, timeout=5)
                self.assertEqual(error.exception.code, 502)
                self.assertNotIn(b'private upstream diagnostics', error.exception.read())
            finally:
                runtime.stop(process)
                provider.shutdown()
                thread.join(timeout=2)
