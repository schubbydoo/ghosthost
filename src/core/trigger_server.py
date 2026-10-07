"""
Trigger Server
==============
Lightweight HTTP server to accept network trigger requests and start playback.
"""

import json
import threading
import time
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

            def do_GET(self):
                """
                What this prop is doing right now, so a caller can tell 'busy'
                from 'broken'.

                Added 2026-08-25 for the SFX box. Purely additive — the POST
                path below is untouched. It answers two questions that were
                previously unanswerable from outside, and which a caller
                otherwise has to guess at:

                  * am I going to be refused, and for how long? The cooldown
                    starts when the AUDIO FINISHES, not when the trigger
                    arrives, so 'time since I last fired it' is not enough to
                    work it out.
                  * what can I ask for? Copying trigger UUIDs by hand between
                    boxes is how the wrong one ends up wired to the wrong
                    button.

                Trigger ids are only listed when the caller could already
                obtain them: if no trigger has a secret then POST is
                unauthenticated anyway and the ids are effectively public; if
                any trigger does have one, listing ids requires presenting a
                valid secret. Names are always listed, so the endpoint is still
                useful for a human without handing out the keys.
                """
                parsed = urlparse(self.path)
                if parsed.path.strip('/') != 'api/status':
                    return self._json_response(404, {'success': False,
                                                     'message': 'Not found'})

                eh = outer.event_handler
                sm = eh.sensor_manager
                cooling = sm.is_in_cooldown()
                remaining = 0.0
                if cooling:
                    remaining = max(0.0, sm.cooldown_end_time - time.time())

                triggers = outer._get_triggers()
                secrets = {(t.get('secret') or '').strip()
                           for t in triggers} - {''}
                may_list_ids = not secrets
                if secrets:
                    auth_header = self.headers.get('Authorization', '')
                    if auth_header.startswith('Bearer '):
                        if auth_header[len('Bearer '):].strip() in secrets:
                            may_list_ids = True
                    q = parse_qs(parsed.query)
                    if 'token' in q and q['token'][0] in secrets:
                        may_list_ids = True

                return self._json_response(200, {
                    'success': True,
                    'kind': 'ghosthost',
                    'performing': bool(eh.performance_active),
                    'cooling_down': bool(cooling),
                    'cooldown_remaining': round(remaining, 1),
                    'cooldown_period': sm.sensor_settings.get(
                        'cooldown_period', 30),
                    # The fact a caller cannot deduce: the clock starts at the
                    # END of the audio, so a prop is unavailable for the audio
                    # length PLUS this.
                    'cooldown_starts': 'after the audio finishes',
                    'triggers': [{
                        'id': t.get('id') if may_list_ids else None,
                        'name': t.get('name'),
                        'enabled': t.get('enabled', True),
                        'audio_file': t.get('audio_file'),
                        'pool_id': t.get('pool_id') or None,
                        'secret_set': bool((t.get('secret') or '').strip()),
                    } for t in triggers],
                })

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

                # Explicit override > pool (random pick) > fixed file > default.
                # With a pool assigned, trigger_network_performance picks from it.
                if audio_override:
                    audio_file, pool_id = audio_override, None
                elif trigger.get('pool_id'):
                    audio_file, pool_id = None, trigger.get('pool_id')
                else:
                    audio_file = trigger.get('audio_file') or outer.config.get('audio.default_file')
                    pool_id = None

                result = outer.event_handler.trigger_network_performance(audio_file, pool_id)
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



