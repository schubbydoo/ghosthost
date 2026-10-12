"""
Greeting Pools
==============
Pick greetings at random from a named pool of audio files.

Selection uses a "shuffle bag": every greeting in the pool is played once, in
random order, before any is repeated, and the first pick after a reshuffle is
never the greeting that was just played. A pool of N files therefore never
plays the same line twice in a row (when N > 1) and feels random without
long runs of one line.

Only the audio file name is chosen here. The mouth-sync timestamps are looked
up from that name at playback time (MotorController._load_audio_timestamps),
so each greeting in a pool uses its own <name>_timestamps.json.
"""

import logging
import random
import threading
from typing import Dict, List, Optional

from src.core import schedule as sched


class GreetingPicker:
    def __init__(self, config, audio_controller):
        self.config = config
        self.audio_controller = audio_controller
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._bags: Dict[str, List[str]] = {}
        self._last: Dict[str, str] = {}
        self._pos: Dict[str, int] = {}          # in-order playback position per pool
        self._port_pool: Dict[str, str] = {}    # last pool each port/trigger played

    def get_pool(self, pool_id: Optional[str]) -> Optional[dict]:
        if not pool_id:
            return None
        for pool in self.config.get('greeting_pools', []) or []:
            if str(pool.get('id')) == str(pool_id):
                return pool
        return None

    def resolve_pool(self, ref: Optional[str]) -> Optional[str]:
        """Turn an assignment into a pool id: a pool id passes through, a
        'schedule:<id>' reference resolves to its current step's pool."""
        if not sched.is_schedule_ref(ref):
            return ref
        current = sched.resolve(self.config, sched.schedule_id_from_ref(ref))
        if not current:
            self.logger.warning(f"Schedule {ref} not found or has no steps")
            return None
        self.logger.info(f"Schedule '{current['schedule'].get('name')}' step "
                         f"{current['step'].get('at')} ({current['reason']})")
        return current['pool_id']

    def _playable(self, pool: dict) -> List[str]:
        available = set(self.audio_controller.list_audio_files())
        return [f for f in dict.fromkeys(pool.get('files') or []) if f in available]

    def _handle_step_change(self, port: str, pool_id: str, files: List[str]):
        """If this port moved to a different pool, restart that pool so the next
        press gives something new rather than replaying what the port heard."""
        previous_id = self._port_pool.get(port)
        self._port_pool[port] = pool_id
        if previous_id is None or previous_id == pool_id:
            return
        key = str(pool_id)
        previous = self.get_pool(previous_id)
        if (self._order(self.get_pool(pool_id)) == 'in_order'):
            heard = set(self._playable(previous)) if previous else set()
            self._pos[key] = next((i for i, f in enumerate(files) if f not in heard), 0)
        else:
            self._bags.pop(key, None)

    @staticmethod
    def _order(pool: Optional[dict]) -> str:
        return 'in_order' if pool and pool.get('order') == 'in_order' else 'shuffle'

    def pick(self, ref: Optional[str], port: Optional[str] = None) -> Optional[str]:
        """Return the next greeting file for a pool or schedule assignment, or
        None if it is missing or has no playable files (caller should fall back).
        port identifies who is asking (sensor or trigger) for step-change tracking."""
        pool_id = self.resolve_pool(ref)
        pool = self.get_pool(pool_id)
        if not pool:
            if ref:
                self.logger.warning(f"Greeting pool {pool_id or ref} not found")
            return None

        files = self._playable(pool)
        if not files:
            self.logger.warning(f"Greeting pool '{pool.get('name')}' has no playable files")
            return None

        key = str(pool_id)
        with self._lock:
            if port and sched.is_schedule_ref(ref):
                self._handle_step_change(port, pool_id, files)
            if self._order(pool) == 'in_order':
                pos = self._pos.get(key, 0) % len(files)
                choice = files[pos]
                self._pos[key] = (pos + 1) % len(files)
            else:
                choice = self._shuffle_pick(key, files)
            self._last[key] = choice

        self.logger.info(f"Greeting pool '{pool.get('name')}' picked {choice}")
        return choice

    def _shuffle_pick(self, key: str, files: List[str]) -> str:
        # Drop entries removed from the pool or deleted from disk
        bag = [f for f in self._bags.get(key, []) if f in files]
        if not bag:
            bag = files[:]
            random.shuffle(bag)
            last = self._last.get(key)
            if len(bag) > 1 and bag[-1] == last:
                # pop() takes from the end; avoid an immediate repeat
                bag[0], bag[-1] = bag[-1], bag[0]
        choice = bag.pop()
        self._bags[key] = bag
        return choice
