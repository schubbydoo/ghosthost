"""Ghost Host's settings for the shared propkit "AI" tab.

Ghost Host uses one AI service: ElevenLabs speech-to-text, which finds the word timing that moves the mouth
(tools/elevenlabs_stt_timestamps.py, run by the Media tab's "Generate timestamps"). So there is one key and one
model setting; nothing here speaks or writes text. The model is kept in the shared config (ai.stt_model).
"""
import json
import os
import re
import threading
import time
from pathlib import Path

import requests
from propkit import ai

from src.core.config_manager import config

BASE_DIR = str(Path(__file__).resolve().parent.parent.parent)
ENV_FILE = os.path.join(BASE_DIR, ".env")
STATUS_PATH = os.path.join(BASE_DIR, "logs", "key_status.json")
STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
DEFAULT_MODEL = "scribe_v1"
MODEL_RE = re.compile(r"^[A-Za-z0-9._:-]{2,80}$")
TIMEOUT_S = 10
STT_OPTIONS = [("scribe_v1", "scribe_v1 - ElevenLabs speech-to-text with word timing")]
OK, FAIL, UNKNOWN = "ok", "fail", "unknown"


# ---- read / write ---------------------------------------------------------------------------------
def stt_model():
    """The model the timing script uses (read by the web app and passed to the script)."""
    config.load_config()
    m = config.get('ai.stt_model', DEFAULT_MODEL)
    return m if isinstance(m, str) and MODEL_RE.match(m) else DEFAULT_MODEL


def load(profile=None):
    return {"stt_model": stt_model()}


def save(values, profile=None):
    model = (values.get("stt_model") or "").strip()
    if not MODEL_RE.match(model):
        return False, "%s is not a valid model name." % model
    config.load_config()
    config.set('ai.stt_model', model)
    config.save_config()
    return True, "Saved. The next \"Generate timestamps\" uses %s." % model


def defaults(profile=None):
    return {"stt_model": DEFAULT_MODEL}


# ---- key check ------------------------------------------------------------------------------------
def _key():
    return ai.EnvFile(ENV_FILE).read().get("ELEVENLABS_API_KEY", "")


def _item(status, detail):
    return {"name": "ElevenLabs speech-to-text key", "status": status, "detail": detail, "provider": "elevenlabs"}


def check_key():
    """Ask a free metadata endpoint whether the key is accepted. Unreachable is 'unknown', never a failure: the prop
    works offline, so a venue with no internet must not raise an alarm."""
    key = _key()
    if not key:
        return _item(FAIL, "ELEVENLABS_API_KEY is not set")
    try:
        r = requests.get("https://api.elevenlabs.io/v1/models", headers={"xi-api-key": key}, timeout=TIMEOUT_S)
    except requests.exceptions.RequestException as e:
        return _item(UNKNOWN, "Could not reach ElevenLabs (%s)" % type(e).__name__)
    if r.status_code == 200:
        return _item(OK, "Key accepted")
    try:
        detail = r.json().get("detail", {})
    except ValueError:
        detail = {}
    if not isinstance(detail, dict):
        detail = {"message": str(detail)}
    status, message = detail.get("status", ""), detail.get("message", "HTTP %d" % r.status_code)
    if status == "missing_permissions":
        return _item(OK, "Key accepted (restricted key)")     # a key limited to some features still proves it is valid
    if status.startswith("invalid_api_key") or (r.status_code == 401 and not status):
        return _item(FAIL, "Key REJECTED: %s" % message)
    if status in ("quota_exceeded", "insufficient_credits") or "quota" in message.lower():
        return _item(FAIL, "Out of ElevenLabs credits: %s" % message)
    return _item(UNKNOWN, "HTTP %d: %s" % (r.status_code, message))


def run_checks(deep=False):
    item = check_key()
    result = {"overall": {OK: "ok", FAIL: "fail"}.get(item["status"], "warn"), "items": [item],
              "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
        with open(STATUS_PATH, "w") as f:
            json.dump(result, f)
    except OSError:
        pass
    return result


def read_status():
    try:
        with open(STATUS_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def start_background_checks(every_s=6 * 3600):
    """Check the key at start-up and every few hours, so a bad key shows as a banner before the night."""
    def loop():
        time.sleep(15)
        while True:
            try:
                run_checks()
            except Exception:
                pass
            time.sleep(every_s)
    threading.Thread(target=loop, daemon=True).start()


# ---- test: transcribe a short clip with the settings on the page ----------------------------------
def _sample():
    """The shortest clip in the Media list, as a stand-in for a visitor-free test."""
    d = Path(BASE_DIR) / config.get('audio.soundfiles_dir', 'SoundFiles')
    clips = sorted((p for p in d.glob("*.wav") if p.is_file()), key=lambda p: p.stat().st_size)
    return (clips[0].name, "audio/wav", clips[0].read_bytes()) if clips else None


def test(values, profile=None, file=None):
    key = _key()
    if not key:
        return {"ok": False, "text": "", "detail": "No ElevenLabs key is set."}
    model = (values.get("stt_model") or stt_model()).strip()
    if file:
        name, kind, data = file["name"], file["type"], file["data"]
    else:
        s = _sample()
        if not s:
            return {"ok": False, "text": "", "detail": "There is no clip in the Media list to test with."}
        name, kind, data = s
    try:
        r = requests.post(STT_URL, headers={"xi-api-key": key},
                          data={"model_id": model, "timestamps_granularity": "word", "tag_audio_events": "true"},
                          files={"file": (name, data, kind)}, timeout=60)
    except requests.exceptions.RequestException as e:
        return {"ok": False, "text": "", "detail": "Could not reach ElevenLabs (%s)." % type(e).__name__}
    if r.status_code != 200:
        try:
            msg = r.json().get("detail", {})
            msg = msg.get("message", "") if isinstance(msg, dict) else str(msg)
        except ValueError:
            msg = ""
        return {"ok": False, "text": "", "detail": "ElevenLabs answered HTTP %d: %s" % (r.status_code, msg[:200])}
    res = r.json()
    words = [w for w in res.get("words", []) if w.get("type") == "word"]
    first = " ".join((res.get("text") or "").split()[:12])
    return {"ok": True, "text": first,
            "detail": "Heard %d words timed in %s using %s (nothing was saved)." % (len(words), name, model)}


# ---- the propkit description ----------------------------------------------------------------------
def build():
    return ai.AIConfig(
        providers=[ai.Provider("elevenlabs", "ElevenLabs", "ELEVENLABS_API_KEY")],
        sections=[ai.Section("models", "Models", help="Applies the next time you press Generate timestamps on the Media tab.", fields=[
            ai.Field("stt_model", "", "model", role="listen", options=STT_OPTIONS,
                     help="Here: finds the word timing for the mouth.")])],
        load=load, save=save, defaults=defaults, test=test, test_label="Test: time the words in a clip",
        test_accepts="audio/*", test_input="the shortest clip in the Media list",
        health=run_checks, last_health=read_status, env_file=ENV_FILE,
        intro="The one AI service Ghost Host uses: it finds when each word is spoken so the mouth moves with the audio. Keys are never shown in full.")
