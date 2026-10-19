"""
Timed Triggers
==============
A timed trigger plays a clip, pool or schedule once at a set local time on a
party night, with no sensor or network request involved (e.g. the costume
contest announcement at 8:30 PM).

Rules:
  * It fires once per party night. The result is kept in a small state file, so
    a restart at 8:31 does not announce it again.
  * It only fires on a trusted clock (see schedule.clock_state).
  * If the prop is busy (speaking, or in its sensor cooldown) at the due time it
    waits and plays as soon as it is free, for up to WAIT_LIMIT_MINUTES. After
    that the announcement is skipped for the night, so a late boot never plays
    an old announcement.
  * It plays through the normal performance path, so the sensor cooldown starts
    when it finishes.

Times before the night rollover (06:00) count as after midnight of the same
party night, the same as pool schedules.
"""

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

from src.core import schedule as sched

WAIT_LIMIT_MINUTES = 5
STATE_FILE = 'timed_trigger_state.json'

logger = logging.getLogger(__name__)

# party_night() and step_minutes() read the rollover from a schedule-shaped dict
_NIGHT = {'night_rollover': sched.DEFAULT_ROLLOVER}


def state_path(config) -> Path:
    return Path(config.config_path).parent / STATE_FILE


def load_state(config) -> dict:
    try:
        with open(state_path(config)) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(config, state: dict):
    path = state_path(config)
    tmp = path.with_suffix('.tmp')
    try:
        with open(tmp, 'w') as f:
            json.dump(state, f)
        os.replace(tmp, path)
    except OSError as e:
        logger.error(f"Could not save timed trigger state: {e}")


def due_minutes(trigger: dict) -> Optional[int]:
    """Minutes into the party night the trigger is due, or None if its time is invalid."""
    if sched.parse_hhmm(trigger.get('time')) is None:
        return None
    return sched.step_minutes({'at': trigger['time']}, _NIGHT)


def tonight(now):
    """(party night date, minutes into that night)"""
    return sched.party_night(now, _NIGHT)


def evaluate(trigger: dict, now, state: dict) -> dict:
    """Where a trigger stands for the current party night.

    status: disabled | wrong_date | waiting | due | played | missed | failed
    'due' means it should fire now (or keep trying, until it times out).
    """
    if not trigger.get('enabled', True):
        return {'status': 'disabled'}
    due = due_minutes(trigger)
    if due is None or not (trigger.get('audio_file') or trigger.get('pool_id')):
        # No target: with neither set the performance path would play the default audio
        return {'status': 'disabled'}
    night, minutes = tonight(now)
    active_date = (trigger.get('active_date') or '').strip()
    if active_date and night.isoformat() != active_date:
        return {'status': 'wrong_date'}
    done = state.get(str(trigger.get('id'))) or {}
    if done.get('night') == night.isoformat():
        return {'status': done.get('result', 'played'), 'at': done.get('at')}
    if minutes < due:
        return {'status': 'waiting', 'in_minutes': due - minutes}
    if minutes - due > WAIT_LIMIT_MINUTES:
        return {'status': 'missed'}
    return {'status': 'due'}


class TimedTriggerRunner:
    def __init__(self, event_handler, config):
        self.event_handler = event_handler
        self.config = config
        self._thread = None
        self._running = False
        # Used instead of the state file while the clock is a test clock, so
        # trying a trigger with a fake time never marks a real night as done
        self._test_state = {}

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name='timed-triggers')
        self._thread.start()
        logger.info("Timed trigger runner started")

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.error(f"Timed trigger check failed: {e}")
            time.sleep(1)

    def _tick(self):
        # The web UI edits the config in another process; this is cached by mtime
        self.config.load_config()
        triggers = self.config.get('timed_triggers', []) or []
        if not triggers:
            return
        clock = sched.clock_state(self.config)
        if not clock['trusted']:
            return
        now = clock['now']
        is_test = clock['state'] == 'test'
        state = self._test_state if is_test else load_state(self.config)
        night = tonight(now)[0].isoformat()

        for trigger in triggers:
            result = evaluate(trigger, now, state)
            key = str(trigger.get('id'))
            if result['status'] == 'missed':
                logger.warning(f"Timed trigger '{trigger.get('name')}' missed its window; skipped for tonight")
                self._record(state, key, night, 'missed', is_test)
            elif result['status'] == 'due':
                self._fire(trigger, state, key, night, is_test)

    def _fire(self, trigger, state, key, night, is_test):
        eh = self.event_handler
        if eh.performance_active or eh.sensor_manager.is_in_cooldown():
            return  # busy: try again next second, until the wait limit
        outcome = eh.trigger_network_performance(
            trigger.get('audio_file') or None, trigger.get('pool_id') or None, f'timed:{key}')
        if outcome.get('success'):
            logger.info(f"Timed trigger '{trigger.get('name')}' started")
            self._record(state, key, night, 'played', is_test)
        elif outcome.get('message') in ('Performance already active', 'In cooldown period'):
            return
        else:
            logger.error(f"Timed trigger '{trigger.get('name')}' could not play: {outcome.get('message')}")
            self._record(state, key, night, 'failed', is_test)

    def _record(self, state, key, night, result, is_test):
        state[key] = {'night': night, 'result': result, 'at': time.strftime('%H:%M:%S')}
        if not is_test:
            save_state(self.config, state)
