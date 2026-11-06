"""What Ghost Host can do, and what it cannot yet, in a fixed shape a program can read.

Served by propkit at `GET /api/capabilities` (readable by read and build tokens), so an MCP server (propmcp)
learns the prop's abilities from the prop and not from its own code. Entries that are NOT installed say why, so
an AI can answer "this prop can't do that" instead of guessing.

Every installed capability names something real in PROOFS (a web route, a module or a file). The test in
tests/test_capabilities.py checks each one exists, and that no major route family in the web app is left
unexplained, so this list cannot quietly drift from the code. Descriptions stay short and factual.
"""
import os
import subprocess

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _cap(id_, label, description, *, installed=True, since="", plain=None, example="", reason=""):
    return {"id": id_, "label": label, "description": description, "installed": installed, "since": since if installed else "",
            "ops": [], "plain": plain or [], "example": example, "reason": reason}


CAPABILITIES = [
    # ---- installed -----------------------------------------------------------------------------------
    _cap("play.sensors", "Motion and pressure sensors",
         "Two sensor ports (left and right) each start a performance when they detect someone. A port plays one clip, a pool (a different "
         "clip each time) or a schedule. A port can be switched off, a sensor must stay active for a minimum time to count (adjustable), "
         "and a cooldown follows every performance.",
         plain=["Switch off the motion sensor and use the pressure pad", "Make the cooldown 30 seconds"]),
    _cap("play.network_trigger", "Network triggers",
         "Named web triggers (a POST to port 5055, with an optional secret) that play a clip or a pool, advance the clue schedule by one step, "
         "or return it to automatic. Other props or a phone can call them.",
         plain=["Add a trigger that plays the greeting when the door opens"]),
    _cap("play.live", "Live tab",
         "Operator controls for the night: message buttons that play a clip now, a button per sensor port that runs it as a visitor would, "
         "a Stop button, and a sensor test. Nothing here changes how the prop is set up.",
         plain=["Play the Tiki greeting now", "Stop him"]),
    _cap("triggers.timed", "Timed triggers",
         "Play a clip, pool or schedule once at a set clock time on a party night, optionally on one date. If the prop is busy it waits up to "
         "5 minutes, then skips it. Needs a trusted clock.",
         plain=["At 8:30 PM play the costume contest announcement once"]),
    _cap("pools", "Pools",
         "Group clips into a pool. A pool plays in shuffled order (every clip once before any repeats) or in the order listed.",
         plain=["Make a pool of the six clue clips, in order"]),
    _cap("schedules", "Pool schedules",
         "An ordered list of steps, each naming a pool and the time it takes over. A sensor port or network trigger assigned to a schedule "
         "plays from whichever step is current. A step can be advanced by hand or returned to automatic; the clock or a test time can be set.",
         plain=["Give the clue button a new hint each hour", "Move to the next clue now"]),
    _cap("shows", "Shows",
         "Save the Triggers settings (default sound, what each port and trigger plays, cooldown, timed triggers, Live buttons) as a named show "
         "and switch between shows on the day.", since="2026-10-22",
         plain=["Save this as the Mill Market show", "Switch to the Friday show"]),
    _cap("media.library", "Sound library",
         "Upload several sounds at once (mp3, m4a, ogg and flac are converted to WAV), describe them, boost one louder or quieter, rename "
         "(pools and triggers follow), play one on the prop, and delete (with a warning when it is in use).", since="2026-11-03",
         plain=["Upload these three clips", "Make the Nosferatu intro 6 dB louder"]),
    _cap("media.mouth_sync", "Mouth-sync timing",
         "Finds when each word of a clip is spoken (ElevenLabs speech-to-text) so the jaw moves with the audio. Needs an ElevenLabs key. "
         "Runs one clip at a time in the background; a failure never blocks an upload.", since="2026-11-03",
         plain=["Time the words in the new greeting"]),
    _cap("idle.look_around", "Idle look-around",
         "While nobody is triggering it, the head looks around every set number of seconds for a set duration; it can be switched off.",
         plain=["Have him look around every two minutes"]),
    _cap("stats.dashboard", "Activity dashboard",
         "Each performance is recorded as one event: where it came from (sensor, network trigger, timer or Live tab), the clip, how long it "
         "ran, and whether it played, failed or was stopped. Shown on the Dashboard, and readable at /api/stats and /api/events.", since="2026-11-03",
         plain=["How many times did he play last night?"]),
    _cap("ai.stt_model", "Speech-to-text setting",
         "The one AI setting: which ElevenLabs speech-to-text model times the mouth. The key is checked at start-up and every 6 hours.", since="2026-11-03"),
    _cap("hardware.animatronic", "Head, torso, mouth motors and eyes",
         "Needs the Ghost Host's Raspberry Pi with the motor driver, LED eyes and sensors wired to its GPIO pins. Without that hardware the "
         "settings still save but nothing moves."),
    # ---- not installed -------------------------------------------------------------------------------
    _cap("speak.text", "Speak typed or sent text", "Say a sentence that was typed or sent live.", installed=False,
         reason="Ghost Host only plays recorded sound files; it has no text-to-speech. A voice clip must be uploaded (and timed) first."),
    _cap("fire.other_props", "Start other props", "Make another prop play something as a step in a show.", installed=False,
         reason="Other props can trigger Ghost Host, but Ghost Host has no step or action that triggers them."),
    _cap("ai.write_lines", "AI-written lines", "Write or choose what he says with AI.", installed=False,
         reason="Every line is a recorded clip; no AI writes or chooses the words."),
]

# Each installed capability must be backed by real code. ("route", url rule) | ("module", dotted name) | ("file", path from the repo root)
PROOFS = {
    "play.sensors": [("route", "/api/sensor_pools"), ("route", "/api/sensor_enabled"), ("route", "/api/config/cooldown"), ("route", "/api/config/sensor_filter"),
                     ("module", "src.hardware.sensor_manager")],
    "play.network_trigger": [("route", "/api/network_triggers"), ("module", "src.core.trigger_server")],
    "play.live": [("route", "/api/live/play"), ("route", "/api/live/stop"), ("route", "/api/live/state")],
    "triggers.timed": [("route", "/api/timed_triggers"), ("module", "src.core.timed_triggers")],
    "pools": [("route", "/api/greeting_pools"), ("module", "src.core.greeting_pool")],
    "schedules": [("route", "/api/schedules"), ("route", "/api/schedule/advance"), ("route", "/api/schedule/auto"),
                  ("route", "/api/schedule/clock"), ("route", "/api/schedule/test_time"), ("module", "src.core.schedule")],
    "shows": [("route", "/api/shows"), ("module", "src.core.shows")],
    "media.library": [("route", "/media"), ("route", "/api/files/upload"), ("module", "src.core.media_library")],
    "media.mouth_sync": [("file", "tools/elevenlabs_stt_timestamps.py"), ("module", "src.core.media_library")],
    "idle.look_around": [("route", "/api/idle_behavior"), ("file", "look_around.py")],
    "stats.dashboard": [("route", "/dashboard"), ("route", "/api/events")],
    "ai.stt_model": [("route", "/ai"), ("module", "src.core.ai_settings")],
    "hardware.animatronic": [("module", "src.hardware.motor_controller"), ("module", "src.hardware.led_controller")],
}

# Route families in the web app that need no capability of their own (status pages, helpers, propkit's shared pages)
SHARED_OR_SUPPORT = ("/static", "/api/health", "/api/status", "/api/audio", "/api/system", "/api/netguard", "/api/updates", "/api/ai",
                     "/api/banner", "/api/capabilities", "/api/link", "/api/files", "/api/stats", "/api/events", "/api/tokens", "/api/wifi", "/api/account",
                     "/api/schedule/status", "/api/live", "/system", "/login", "/logout", "/setup", "/wifi", "/add-network", "/connect-",
                     "/delete-network", "/")


def capabilities():
    return CAPABILITIES


def app_version():
    """The prop's own version: the git short id of the checkout it is running."""
    try:
        return subprocess.run(["git", "-C", _BASE, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""
