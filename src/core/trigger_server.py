"""
Trigger Server
==============
Lightweight HTTP server to accept network trigger requests and start playback.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs


class TriggerServer:
    def __init__(self, event_handler, config):
        self.event_handler = event_handler
        self.config = config
        self.server = None
        self.thread = None

    def _get_triggers(self):
        # Reload config so new/updated triggers are visible without restarting main app
        try:
            self.config.load_config()
        except Exception:
            pass
        return self.config.get('network_triggers', []) or []

    def _find_trigger(self, trigger_id: str):
        for t in self._get_triggers():
            if str(t.get('id')) == str(trigger_id):
                return t
        return None

    def _make_handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _json_response(self, code: int, payload: dict):
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode('utf-8'))

            def do_POST(self):
                parsed = urlparse(self.path)
                parts = parsed.path.strip('/').split('/')

                # Accept only /api/trigger/<id>/play
                if not (len(parts) == 4 and parts[0] == 'api' and parts[1] == 'trigger' and parts[3] == 'play'):
                    return self._json_response(404, {'success': False, 'message': 'Not found'})

                trigger_id = parts[2]
                trigger = outer._find_trigger(trigger_id)
                if not trigger or not trigger.get('enabled', True):
                    return self._json_response(404, {'success': False, 'message': 'Trigger not found'})

                # Auth via bearer header or token query
                secret = (trigger.get('secret') or '').strip()
                if secret:
                    auth_ok = False
                    auth_header = self.headers.get('Authorization', '')
                    if auth_header.startswith('Bearer '):
                        token = auth_header[len('Bearer '):].strip()
                        if token == secret:
                            auth_ok = True
                    if not auth_ok:
                        # check query param
                        q = parse_qs(parsed.query)
                        if 'token' in q and q['token'][0] == secret:
                            auth_ok = True
                    if not auth_ok:
                        return self._json_response(401, {'success': False, 'message': 'Unauthorized'})

                # Read optional body to override audio_file
                length = int(self.headers.get('Content-Length', 0) or 0)
                audio_override = None
                if length > 0:
                    try:
                        body = self.rfile.read(length)
                        data = json.loads(body.decode('utf-8'))
                        audio_override = data.get('audio_file')
                    except Exception:
                        pass

                audio_file = audio_override or trigger.get('audio_file') or outer.config.get('audio.default_file')

                result = outer.event_handler.trigger_network_performance(audio_file)
                if result.get('success'):
                    return self._json_response(200, result)
                msg = result.get('message', 'Busy')
                code = 409 if msg in ('Performance already active', 'In cooldown period') else 400
                return self._json_response(code, result)

            def log_message(self, format, *args):
                # Silence default logging; integrate with main logs if desired
                return

        return Handler

    def start(self):
        settings = self.config.get('network_trigger', {})
        port = int(settings.get('port', 5055))
        self.server = HTTPServer(('0.0.0.0', port), self._make_handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        return True



