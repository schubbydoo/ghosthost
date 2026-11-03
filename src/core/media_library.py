"""Ghost Host's side of the shared propkit Media tab.

propkit draws the page and does the safe generic parts (names, content check, size and disk limits, duplicates,
atomic saves, delete warnings). This module supplies what is specific to Ghost Host:

  * GhostStore   - the SoundFiles folder, where every upload becomes a real .wav (mp3, m4a, ogg and flac are converted),
                   descriptions / boosts / Live-tab picks live in the shared config, and a clip's
                   <name>_timestamps.json travels with it (deleted with it)
  * timing       - mouth-sync timing through ElevenLabs, one file at a time in a background worker, so a slow or
                   offline provider can never block an upload or a request
  * actions      - Time the words, Use as default sound, Put on / Remove from the Live tab, Set boost (dB)
  * usage        - where a clip is used (pools, triggers, sensor ports, shows, the default), as links
"""
import json
import os
import queue
import subprocess
import sys
import threading
import wave
from pathlib import Path

from propkit.files import Facet, FileAction, FileLibrary, Option, Param, clean_name

from src.core.config_manager import config

BASE_DIR = str(Path(__file__).resolve().parent.parent.parent)
SCRIPT = os.path.join(BASE_DIR, "tools", "elevenlabs_stt_timestamps.py")
BATCH_LIMIT = 10          # timing jobs accepted per press: each one is a network call to ElevenLabs
TIMING_TIMEOUT_S = 120


def _soundfiles_dir():
    return os.path.join(BASE_DIR, config.get('audio.soundfiles_dir', 'SoundFiles'))


def _sidecar(name):
    return os.path.splitext(name)[0] + "_timestamps.json"


def _words_timed(path):
    """Number of timed words in a timing file, or None if there is no usable file."""
    try:
        with open(path) as f:
            data = json.load(f)
        return len([w for w in data.get("words", []) if w.get("type", "word") == "word"])
    except (OSError, ValueError, AttributeError):
        return None


# ---- the store ----------------------------------------------------------------------------------------------
class GhostStore:
    def __init__(self, audio_controller):
        self.ac = audio_controller

    @property
    def root(self):
        return _soundfiles_dir()

    # paths
    def path(self, name, collection=None):
        """Real path of a clip in SoundFiles; ValueError for anything that is not a plain .wav inside it."""
        if clean_name(name) != name or not name.lower().endswith(".wav"):
            raise ValueError("bad name")
        root = os.path.realpath(self.root)
        p = os.path.join(root, name)
        if os.path.islink(p) or os.path.dirname(os.path.realpath(p)) != root:
            raise ValueError("bad path")
        return p

    # reading
    def collections(self):
        return []

    def list(self, collection=None):
        config.load_config()
        descriptions = config.get('audio_descriptions', {}) or {}
        gains = config.get('audio_gains', {}) or {}
        live = set(config.get('live_files', []) or [])
        default = config.get('audio.default_file', '')
        pools_of = {}
        for pool in config.get('greeting_pools', []) or []:
            for f in pool.get('files') or []:
                pools_of.setdefault(f, []).append(str(pool.get('name', '?')))
        out = []
        try:
            names = sorted((n for n in os.listdir(self.root) if n.lower().endswith(".wav") and not n.startswith(".")), key=str.lower)
        except OSError:
            return []
        for n in names:
            p = os.path.join(self.root, n)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            st = os.stat(p)
            words = _words_timed(os.path.join(self.root, _sidecar(n)))
            try:
                with wave.open(p, "rb") as w:
                    seconds = round(w.getnframes() / float(w.getframerate()), 1)
            except (wave.Error, EOFError, OSError, ZeroDivisionError):
                seconds = None
            gain = float(gains.get(n, 0) or 0)
            facts = [["Mouth timing", "%d words timed" % words if words else "none yet"]]
            if gain:
                facts.append(["Boost", "%+g dB" % gain])
            out.append({"id": n, "name": n, "size": st.st_size, "mtime": int(st.st_mtime), "seconds": seconds,
                        "description": descriptions.get(n, ""), "facets": {"pool": pools_of.get(n, [])}, "facts": facts,
                        "extra": {"words": words, "gain": gain, "live": n in live, "default": n == default}})
        return out

    def description(self, name, collection=None):
        return (config.get('audio_descriptions', {}) or {}).get(name, "")

    def usage_bytes(self):
        total = 0
        for n in os.listdir(self.root):
            p = os.path.join(self.root, n)
            if os.path.isfile(p) and not os.path.islink(p):
                total += os.path.getsize(p)
        return total

    # writing
    def save(self, tmp_path, name, collection=None, on_duplicate="ask"):
        """Store an upload as <name without extension>.wav, converting when it is not already a readable WAV.
        Nothing is left behind if the conversion fails."""
        final = os.path.splitext(name)[0] + ".wav"
        dest = self.path(final)
        if os.path.exists(dest):
            if on_duplicate == "skip":
                return {"status": "skipped", "name": final}
            if on_duplicate == "keep_both":
                base, n = os.path.splitext(final)[0], 2
                while os.path.exists(self.path("%s (%d).wav" % (base, n))):
                    n += 1
                final = "%s (%d).wav" % (base, n)
                dest, status = self.path(final), "kept_both"
            elif on_duplicate == "replace":
                status = "replaced"
            else:
                return {"status": "exists", "name": final}
        else:
            status = "saved"
        os.makedirs(self.root, exist_ok=True)
        work = os.path.join(self.root, ".converting-" + final)
        try:
            if self._plain_wav(tmp_path):
                os.replace(tmp_path, work)
            else:
                try:
                    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp_path, "-c:a", "pcm_s16le", "-f", "wav", work],
                                   check=True, capture_output=True, timeout=120)
                except (subprocess.SubprocessError, OSError):
                    raise OSError(5, "That audio could not be converted")
            os.replace(work, dest)
        finally:
            try:
                os.remove(work)
            except OSError:
                pass
        if status == "replaced":                         # the old timing and boosted copy no longer match the new sound
            self._forget_derived(final)
            try:
                os.remove(os.path.join(self.root, _sidecar(final)))
            except OSError:
                pass
        return {"status": status, "name": final}

    @staticmethod
    def _plain_wav(path):
        try:
            with wave.open(path, "rb") as w:
                return w.getnframes() > 0
        except (wave.Error, EOFError, OSError):
            return False

    def _forget_derived(self, name):
        try:
            self.ac.clear_gain_cache(name)
        except Exception:
            pass

    def delete(self, name, collection=None):
        os.remove(self.path(name))
        self._forget_derived(name)
        try:
            os.remove(os.path.join(self.root, _sidecar(name)))
        except OSError:
            pass
        config.load_config()
        for key in ('audio_descriptions', 'audio_gains'):
            d = config.get(key, {}) or {}
            if name in d:
                d.pop(name)
                config.set(key, d)
        live = [f for f in (config.get('live_files', []) or []) if f != name]
        config.set('live_files', live)
        config.save_config()
        _TIMING.pop(name, None)

    def rename(self, name, new, collection=None):
        """Rename the clip and its timing file. The places that refer to it by name are rewritten by rewrite_references()
        (propkit calls that straight after)."""
        src, dst = self.path(name), self.path(new)
        if os.path.exists(dst):
            raise FileExistsError(new)
        os.rename(src, dst)
        try:
            os.rename(os.path.join(self.root, _sidecar(name)), os.path.join(self.root, _sidecar(new)))
        except OSError:
            pass
        self._forget_derived(name)           # the boosted copy is named after the clip: it is made again on the next play

    def preview_path(self, name, collection=None):
        """What the detail panel plays: the clip as the prop plays it (with its boost) when it has one."""
        gain = float((config.get('audio_gains', {}) or {}).get(name, 0) or 0)
        p = self.ac.gain_path(name, gain) if gain else None
        return os.path.abspath(str(p)) if p else None       # the web page serves it from another folder, so it must not be relative

    def describe(self, name, text, collection=None):
        self.path(name)
        config.load_config()
        d = config.get('audio_descriptions', {}) or {}
        if text:
            d[name] = text
        else:
            d.pop(name, None)
        config.set('audio_descriptions', d)
        config.save_config()


def _swap(obj, old, new):
    """Copy of obj with the clip's name replaced wherever it appears as a value ("old.wav" or "file:old.wav")."""
    if isinstance(obj, dict):
        return {k: _swap(v, old, new) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_swap(v, old, new) for v in obj]
    if obj == old:
        return new
    if obj == "file:" + old:
        return "file:" + new
    return obj


def rewrite_references(old, new, collection=None):
    """After a rename, point everything that used the old name at the new one: pools, the default sound, Live buttons,
    sensor ports, network and timed triggers, saved shows, the description and the boost."""
    config.load_config()
    for key in ('greeting_pools', 'live_files', 'sensor_pools', 'network_triggers', 'timed_triggers', 'shows'):
        cur = config.get(key)
        if cur:
            config.set(key, _swap(cur, old, new))
    if config.get('audio.default_file') == old:
        config.set('audio.default_file', new)
    for key in ('audio_descriptions', 'audio_gains'):
        d = dict(config.get(key, {}) or {})
        if old in d:
            d[new] = d.pop(old)
            config.set(key, d)
    config.save_config()


# ---- mouth-sync timing: one file at a time, in the background ----------------------------------------------------
_TIMING = {}                 # name -> ("queued" | "running" | "failed", message)
_JOBS = queue.Queue()
_worker = None
_lock = threading.Lock()


def _friendly(output):
    text = (output or "").strip()
    low = text.lower()
    if "elevenlabs_api_key not found" in low:
        return "no ElevenLabs key is set"
    if any(w in low for w in ("connection", "resolve", "timed out", "unreachable", "max retries")):
        return "ElevenLabs could not be reached (offline?)"
    if "401" in low or "invalid" in low and "key" in low:
        return "ElevenLabs rejected the key"
    if "quota" in low or "credits" in low:
        return "out of ElevenLabs credits"
    return (text.splitlines() or ["it failed"])[-1][:120]


def _time_one(name):
    from src.core import ai_settings
    env = dict(os.environ, ELEVENLABS_STT_MODEL=ai_settings.stt_model())
    try:
        p = subprocess.run([sys.executable, SCRIPT, name], capture_output=True, text=True, timeout=TIMING_TIMEOUT_S, cwd=BASE_DIR, env=env)
    except subprocess.TimeoutExpired:
        return False, "it took too long (over %d s)" % TIMING_TIMEOUT_S
    except OSError as e:
        return False, "could not run the timing script (%s)" % e.strerror
    if p.returncode == 0 and os.path.exists(os.path.join(_soundfiles_dir(), _sidecar(name))):
        return True, ""
    return False, _friendly(p.stderr or p.stdout)


def _work():
    while True:
        name = _JOBS.get()
        _TIMING[name] = ("running", "")
        try:
            ok, msg = _time_one(name)
        except Exception as e:                                   # a bad job must never stop the worker
            ok, msg = False, str(e)[:120]
        if ok:
            _TIMING.pop(name, None)
        else:
            _TIMING[name] = ("failed", msg)


def queue_timing(names):
    """Queue clips for timing. -> {name: {"ok", "message"}}. Only BATCH_LIMIT per call."""
    global _worker
    out = {}
    with _lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_work, daemon=True)
            _worker.start()
        for i, n in enumerate(names):
            if i >= BATCH_LIMIT:
                out[n] = {"ok": False, "message": "Over the limit of %d per press. Press again for the rest." % BATCH_LIMIT}
            elif _TIMING.get(n, ("",))[0] in ("queued", "running"):
                out[n] = {"ok": True, "message": "Already being timed."}
            else:
                _TIMING[n] = ("queued", "")
                _JOBS.put(n)
                out[n] = {"ok": True, "message": "Queued (about 10-20 seconds each)."}
    return out


def _timing_pill(f):
    state = _TIMING.get(f["name"])
    if state and state[0] in ("queued", "running"):
        return {"text": "timing...", "tone": "busy"}      # busy: the page refreshes itself until it is done
    if state and state[0] == "failed":
        return {"text": "timing failed: " + state[1], "tone": "bad"}
    words = f["extra"].get("words")
    if words:
        return {"text": "%d words timed" % words, "tone": "good"}
    return {"text": "no mouth timing", "tone": "warn"}


def _timing_pending(f):
    state = _TIMING.get(f["name"])
    return not f["extra"].get("words") and not (state and state[0] in ("queued", "running"))


def _run_timing(names, options, collection):
    return queue_timing(names)


# ---- the other actions -------------------------------------------------------------------------------------------
def _ok(message="Done."):
    return {"ok": True, "message": message}


def _make_actions(ac):
    def use_default(names, options, collection):
        config.load_config()
        config.set('audio.default_file', names[0])
        config.save_config()
        return {names[0]: _ok("This is now the default sound.")}

    def live_set(on):
        def run(names, options, collection):
            config.load_config()
            live = list(config.get('live_files', []) or [])
            for n in names:
                if on and n not in live:
                    live.append(n)
                if not on and n in live:
                    live.remove(n)
            config.set('live_files', live)
            config.save_config()
            return {n: _ok("On the Live tab." if on else "Removed from the Live tab.") for n in names}
        return run

    def boost(names, options, collection):
        """Set the boost in dB (0 clears it). A boosted copy is made now so the next play starts at once."""
        raw = (options.get("params") or {}).get("db", "")
        if str(raw).strip() == "":
            return {n: {"ok": False, "message": "Type the boost in dB first (for example 3). \"Remove boost\" clears it."} for n in names}
        try:
            db = round(float(raw), 1)
        except (TypeError, ValueError):
            return {n: {"ok": False, "message": "The boost must be a number."} for n in names}
        if not db:
            return {n: {"ok": False, "message": "A boost of 0 does nothing. Use \"Remove boost\" to clear it."} for n in names}
        if not -ac.MAX_GAIN_DB <= db <= ac.MAX_GAIN_DB:
            return {n: {"ok": False, "message": "The boost must be between -%d and %d dB." % (ac.MAX_GAIN_DB, ac.MAX_GAIN_DB)} for n in names}
        config.load_config()
        gains = dict(config.get('audio_gains', {}) or {})
        out = {}
        for n in names:
            ac.clear_gain_cache(n)
            if db:
                if not ac.gain_path(n, db):
                    out[n] = {"ok": False, "message": "Could not make the boosted copy (is ffmpeg installed?)"}
                    continue
                gains[n] = db
            else:
                gains.pop(n, None)
            out[n] = _ok("Boost is now %+g dB." % db if db else "Boost removed.")
        config.set('audio_gains', gains)
        config.save_config()
        return out

    def remove_boost(names, options, collection):
        config.load_config()
        gains = dict(config.get('audio_gains', {}) or {})
        for n in names:
            ac.clear_gain_cache(n)
            gains.pop(n, None)
        config.set('audio_gains', gains)
        config.save_config()
        return {n: _ok("Boost removed.") for n in names}

    return [
        FileAction("timestamps", "Time the words", run=_run_timing, pending=_timing_pending, status=_timing_pill,
                   pending_label="Time all untimed"),
        FileAction("default", "Use as default sound", run=use_default, single_only=True,
                   status=lambda f: {"text": "default sound", "tone": "good"} if f["extra"].get("default") else None),
        FileAction("live_on", "Put on the Live tab", run=live_set(True),
                   status=lambda f: {"text": "on Live tab", "tone": "muted"} if f["extra"].get("live") else None),
        FileAction("live_off", "Remove from the Live tab", run=live_set(False)),
        FileAction("boost", "Set boost", run=boost, params=[Param("db", "Boost (dB)", "number", "", min=-ac.MAX_GAIN_DB, max=ac.MAX_GAIN_DB, step=0.5)],
                   status=lambda f: {"text": "boost %+g dB" % f["extra"]["gain"], "tone": "muted"} if f["extra"].get("gain") else None),
        FileAction("boost_clear", "Remove boost", run=remove_boost),
    ]


# ---- where a clip is used ------------------------------------------------------------------------------------------
def usage(name, collection=None):
    config.load_config()
    out = []
    for pool in config.get('greeting_pools', []) or []:
        if name in (pool.get('files') or []):
            out.append({"label": "Pool: %s" % pool.get('name', '?'), "href": "/#pools"})
    if config.get('audio.default_file') == name:
        out.append({"label": "The default sound", "href": "/#triggers"})
    if name in (config.get('live_files', []) or []):
        out.append({"label": "A Live tab button", "href": "/#live"})
    for port, ref in (config.get('sensor_pools', {}) or {}).items():
        if ref == 'file:' + name:
            out.append({"label": "Sensor port: %s" % port.replace('sensor_port_', ''), "href": "/#triggers"})
    for t in config.get('network_triggers', []) or []:
        if t.get('audio_file') == name:
            out.append({"label": "Network trigger: %s" % t.get('name', '?'), "href": "/#triggers"})
    for t in config.get('timed_triggers', []) or []:
        if t.get('audio_file') == name:
            out.append({"label": "Timed trigger: %s" % t.get('name', '?'), "href": "/#triggers"})
    needle = json.dumps(name)
    for show in config.get('shows', []) or []:
        if needle in json.dumps(show.get('snapshot') or {}):
            out.append({"label": "Saved show: %s" % show.get('name', '?'), "href": "/#triggers"})
    return out


# ---- the propkit description ---------------------------------------------------------------------------------------
def build(audio_controller):
    return FileLibrary(
        kind="audio", noun="sound", store=GhostStore(audio_controller),
        upload_options=[Option("timestamps", "Get the mouth-sync timing after upload", default=True,
                               help="Needs the ElevenLabs key. If it is offline the sound still uploads and the list says why timing failed.")],
        after_upload=lambda names, options, collection: queue_timing(names) if options.get("timestamps") else None,
        actions=_make_actions(audio_controller), usage=usage, allow_rename=True, on_rename=rewrite_references,
        facets=[Facet("pool", "Pool")],
        intro="Upload, find and manage the sounds the prop plays. Pools, triggers and the Live tab pick from these.")
