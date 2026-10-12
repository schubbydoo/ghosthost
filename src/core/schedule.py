"""
Pool Schedules
==============
A schedule is an ordered list of steps, each naming an existing greeting pool and
the local time it takes over. A sensor port (or network trigger) assigned to a
schedule plays from whichever step is current, so a clue button can hand out
new hints as the night goes on.

Everything here is pure logic over the config plus the system clock, so both the
main app (playback) and the web app (status panel) share one implementation.

Assignments are stored in the existing pool fields as "schedule:<schedule id>".
"""

import logging
import os
import subprocess
from datetime import datetime, timedelta
from typing import Optional

SCHEDULE_PREFIX = 'schedule:'
DEFAULT_ROLLOVER = '06:00'
# Marks a hand-set clock; holds the boot id so it expires on reboot
CLOCK_FLAG_PATH = '/tmp/ghosthost_clock_manual'

logger = logging.getLogger(__name__)


def is_schedule_ref(ref) -> bool:
    return isinstance(ref, str) and ref.startswith(SCHEDULE_PREFIX)


def schedule_ref(schedule_id: str) -> str:
    return SCHEDULE_PREFIX + str(schedule_id)


def schedule_id_from_ref(ref: str) -> str:
    return ref[len(SCHEDULE_PREFIX):]


def parse_hhmm(value) -> Optional[int]:
    """'20:30' -> minutes since midnight, or None if invalid."""
    try:
        h, m = str(value).split(':')
        h, m = int(h), int(m)
    except (ValueError, AttributeError):
        return None
    if 0 <= h < 24 and 0 <= m < 60:
        return h * 60 + m
    return None


def get_schedule(config, schedule_id) -> Optional[dict]:
    for s in config.get('schedules', []) or []:
        if str(s.get('id')) == str(schedule_id):
            return s
    return None


# --- Clock ---

def _boot_id() -> str:
    try:
        with open('/proc/sys/kernel/random/boot_id') as f:
            return f.read().strip()
    except OSError:
        return ''


def mark_clock_manual():
    try:
        with open(CLOCK_FLAG_PATH, 'w') as f:
            f.write(_boot_id())
    except OSError as e:
        logger.warning(f"Could not record manual clock flag: {e}")


def _clock_set_manually() -> bool:
    try:
        with open(CLOCK_FLAG_PATH) as f:
            return f.read().strip() == _boot_id()
    except OSError:
        return False


def _ntp_synced() -> bool:
    try:
        out = subprocess.run(['timedatectl', 'show', '-p', 'NTPSynchronized', '--value'],
                             capture_output=True, text=True, timeout=3).stdout
        return out.strip().lower() == 'yes'
    except Exception:
        return False


def clock_state(config) -> dict:
    """{'now': datetime, 'state': synced|manual|test|unset, 'trusted': bool}"""
    test = config.get('schedule_test_time')
    if test:
        try:
            return {'now': datetime.fromisoformat(str(test)), 'state': 'test', 'trusted': True}
        except ValueError:
            logger.warning(f"Ignoring invalid schedule_test_time {test!r}")
    now = datetime.now()
    if _ntp_synced():
        return {'now': now, 'state': 'synced', 'trusted': True}
    if _clock_set_manually():
        return {'now': now, 'state': 'manual', 'trusted': True}
    return {'now': now, 'state': 'unset', 'trusted': False}


# --- Schedule math ---

def rollover_minutes(schedule: dict) -> int:
    value = parse_hhmm(schedule.get('night_rollover') or DEFAULT_ROLLOVER)
    return value if value is not None else parse_hhmm(DEFAULT_ROLLOVER)


def party_night(now: datetime, schedule: dict):
    """(date of the party night, minutes into that night). Times before the
    rollover hour belong to the previous calendar day's night."""
    minutes = now.hour * 60 + now.minute
    night = now.date()
    if minutes < rollover_minutes(schedule):
        night = night - timedelta(days=1)
        minutes += 24 * 60
    return night, minutes


def step_minutes(step: dict, schedule: dict) -> int:
    """Minutes into the night a step starts. Times between 00:01 and the rollover
    hour sort after midnight; 00:00 itself is the starting step."""
    m = parse_hhmm(step.get('at')) or 0
    if 0 < m < rollover_minutes(schedule):
        m += 24 * 60
    return m


def sorted_steps(schedule: dict) -> list:
    return sorted(schedule.get('steps') or [], key=lambda s: step_minutes(s, schedule))


def _override_step(config, schedule: dict, now: datetime) -> Optional[int]:
    """Manual step index, unless it was set on an earlier party night."""
    ov = config.get('schedule_override') or {}
    if ov.get('step') is None or not ov.get('set_at'):
        return None
    try:
        set_at = datetime.fromisoformat(str(ov['set_at']))
    except ValueError:
        return None
    if party_night(set_at, schedule)[0] != party_night(now, schedule)[0]:
        return None
    return int(ov['step'])


def resolve(config, schedule_id) -> Optional[dict]:
    """Work out the current step of a schedule.

    Returns {'schedule', 'index', 'step', 'pool_id', 'next', 'reason', 'clock'}
    or None if the schedule is missing or empty. index is into sorted_steps.
    """
    schedule = get_schedule(config, schedule_id)
    if not schedule:
        return None
    steps = sorted_steps(schedule)
    if not steps:
        return None
    clock = clock_state(config)
    now = clock['now']
    night, minutes = party_night(now, schedule)

    override = _override_step(config, schedule, now)
    active_date = (schedule.get('active_date') or '').strip()
    if override is not None:
        index, reason = max(0, min(override, len(steps) - 1)), 'override'
    elif not clock['trusted']:
        index, reason = 0, 'clock not set'
    elif active_date and night.isoformat() != active_date:
        index, reason = 0, 'not the active date'
    else:
        index = 0
        for i, s in enumerate(steps):
            if step_minutes(s, schedule) <= minutes:
                index = i
        reason = 'time'

    nxt = None
    if index + 1 < len(steps) and reason == 'time':
        nxt = steps[index + 1].get('at')
    return {'schedule': schedule, 'index': index, 'step': steps[index],
            'pool_id': steps[index].get('pool_id'), 'next': nxt,
            'reason': reason, 'clock': clock}


def set_override(config, schedule_id, delta_or_none) -> Optional[dict]:
    """Advance one step from the current one, or clear the override (None)."""
    if delta_or_none is None:
        config.set('schedule_override', {'step': None, 'set_at': None})
        config.save_config()
        return None
    current = resolve(config, schedule_id)
    if not current:
        return None
    count = len(sorted_steps(current['schedule']))
    step = min(current['index'] + 1, count - 1)
    config.set('schedule_override', {'step': step, 'set_at': current['clock']['now'].isoformat()})
    config.save_config()
    return current


def set_system_clock(epoch_seconds: int) -> bool:
    """Set the Pi's clock (needs a sudoers entry for `date`)."""
    try:
        subprocess.run(['sudo', '-n', 'date', '-s', f'@{int(epoch_seconds)}'],
                       check=True, capture_output=True, timeout=5)
    except Exception as e:
        logger.error(f"Failed to set system clock: {e}")
        return False
    mark_clock_manual()
    return True


def assigned_schedule_ids(config) -> list:
    """Schedules currently assigned to a sensor port, in port order."""
    ids = []
    for port in ('sensor_port_left', 'sensor_port_right'):
        ref = (config.get('sensor_pools', {}) or {}).get(port)
        if is_schedule_ref(ref) and schedule_id_from_ref(ref) not in ids:
            ids.append(schedule_id_from_ref(ref))
    return ids


def advance_assigned(config) -> bool:
    """Advance to the next step of the first scheduled port. The override is a
    single step number, shared by every schedule."""
    ids = assigned_schedule_ids(config)
    if not ids:
        return False
    return set_override(config, ids[0], 1) is not None
