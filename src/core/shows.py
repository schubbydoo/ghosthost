"""
Shows
=====
A show is a saved set of the settings that change from one event to the next:
what plays when nothing is assigned, what each sensor port and network trigger
plays, the sensor cooldown, and the timed triggers. Pools, pool schedules, the
audio library and its gains and descriptions are shared by every show.

The live config keys stay the single source of truth, so nothing else in the
app knows about shows. A show is a snapshot of those keys: switching to a show
copies its snapshot into the live config, and "save" copies the live config
back into the show. The show is "modified" when the live settings differ from
its snapshot.
"""

import copy
import json
import uuid
from typing import Optional

from src.core import schedule as sched

SENSOR_PORTS = ('sensor_port_left', 'sensor_port_right')
# Per network trigger, only what it plays. Name, secret and id belong to the
# trigger itself because other devices are wired to them.
TRIGGER_FIELDS = ('enabled', 'audio_file', 'pool_id', 'action')


def capture(config) -> dict:
    """Snapshot of the live settings that make up a show."""
    assignments = config.get('sensor_pools', {}) or {}
    return {
        'default_file': config.get('audio.default_file', '') or '',
        'cooldown_period': config.get('sensors.cooldown_period', 30),
        'sensor_pools': {p: assignments.get(p) or '' for p in SENSOR_PORTS},
        'network_triggers': {
            str(t.get('id')): {
                'enabled': t.get('enabled', True),
                'audio_file': t.get('audio_file') or '',
                'pool_id': t.get('pool_id') or '',
                'action': t.get('action') or 'play',
            } for t in config.get('network_triggers', []) or []},
        'timed_triggers': copy.deepcopy(config.get('timed_triggers', []) or []),
    }


def _same(a, b) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def is_modified(config, show: dict) -> bool:
    return not _same(capture(config), show.get('snapshot') or {})


def get_show(config, show_id) -> Optional[dict]:
    for s in config.get('shows', []) or []:
        if str(s.get('id')) == str(show_id):
            return s
    return None


def ref_ok(config, ref, files=None) -> bool:
    """A pool id, 'schedule:<id>' naming an existing schedule, or (for sensor
    ports, when `files` is given) 'file:<name>' naming an existing clip."""
    if not ref:
        return True
    if isinstance(ref, str) and ref.startswith('file:'):
        return files is not None and ref[len('file:'):] in files
    if sched.is_schedule_ref(ref):
        return sched.get_schedule(config, sched.schedule_id_from_ref(ref)) is not None
    return any(str(p.get('id')) == str(ref) for p in config.get('greeting_pools', []) or [])


def fresh_ids(snapshot: dict) -> dict:
    """Copy of a snapshot with new timed trigger ids, so two shows never share one
    (a trigger's once-per-night record is keyed by its id)."""
    snap = copy.deepcopy(snapshot)
    for t in snap.get('timed_triggers', []):
        t['id'] = str(uuid.uuid4())
    return snap


def apply(config, snapshot: dict, audio_files) -> list:
    """Copy a snapshot into the live config. Anything it names that no longer
    exists (a deleted pool or clip) is dropped, never played as a fallback.
    Returns human-readable warnings. The caller saves the config."""
    warnings = []
    files = set(audio_files)

    default = snapshot.get('default_file') or ''
    if default and default not in files:
        warnings.append(f"Default audio '{default}' no longer exists; kept the current default")
    elif default:
        config.set('audio.default_file', default)

    if snapshot.get('cooldown_period') is not None:
        config.set('sensors.cooldown_period', snapshot['cooldown_period'])

    pools = {}
    for port in SENSOR_PORTS:
        ref = (snapshot.get('sensor_pools') or {}).get(port) or ''
        if not ref_ok(config, ref, files):
            warnings.append(f"{port.replace('sensor_port_', '').title()} sensor's pool no longer exists; it plays the default audio")
            ref = ''
        pools[port] = ref
    config.set('sensor_pools', pools)

    saved = snapshot.get('network_triggers') or {}
    for t in config.get('network_triggers', []) or []:
        mine = saved.get(str(t.get('id')))
        if not mine:
            continue
        for field in TRIGGER_FIELDS:
            if field in mine:
                t[field] = mine[field]
        if t.get('pool_id') and not ref_ok(config, t['pool_id']):
            warnings.append(f"Network trigger '{t.get('name')}' used a pool that no longer exists")
            t['pool_id'] = ''
        if t.get('audio_file') and t['audio_file'] not in files:
            warnings.append(f"Network trigger '{t.get('name')}' used a clip that no longer exists")
            t['audio_file'] = ''

    timed = copy.deepcopy(snapshot.get('timed_triggers') or [])
    for t in timed:
        bad = (t.get('audio_file') and t['audio_file'] not in files) or not ref_ok(config, t.get('pool_id'))
        if bad:
            warnings.append(f"Timed trigger '{t.get('name')}' lost its clip or pool and was switched off")
            t['audio_file'], t['pool_id'], t['enabled'] = '', '', False
    config.set('timed_triggers', timed)

    # A hand-advanced pool schedule belongs to the previous show
    config.set('schedule_override', {'step': None, 'set_at': None})
    return warnings


def summary(config, snapshot: dict) -> dict:
    """What a show does, in plain terms, for the UI."""
    def ref_label(ref):
        if not ref:
            return 'default audio'
        if isinstance(ref, str) and ref.startswith('file:'):
            return ref[len('file:'):]
        if sched.is_schedule_ref(ref):
            sc = sched.get_schedule(config, sched.schedule_id_from_ref(ref))
            return 'Schedule: ' + sc['name'] if sc else '(missing)'
        pool = next((p for p in config.get('greeting_pools', []) or [] if str(p.get('id')) == str(ref)), None)
        return pool['name'] if pool else '(missing)'
    ports = snapshot.get('sensor_pools') or {}
    timed = snapshot.get('timed_triggers') or []
    return {
        'default_file': snapshot.get('default_file') or '',
        'left': ref_label(ports.get('sensor_port_left')),
        'right': ref_label(ports.get('sensor_port_right')),
        'cooldown': snapshot.get('cooldown_period'),
        'timed': sorted([f"{t.get('time')} {t.get('name')}" for t in timed if t.get('enabled', True)]),
    }
