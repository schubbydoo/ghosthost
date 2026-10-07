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


class GreetingPicker:
    def __init__(self, config, audio_controller):
        self.config = config
        self.audio_controller = audio_controller
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._bags: Dict[str, List[str]] = {}
        self._last: Dict[str, str] = {}

    def get_pool(self, pool_id: Optional[str]) -> Optional[dict]:
        if not pool_id:
            return None
        for pool in self.config.get('greeting_pools', []) or []:
            if str(pool.get('id')) == str(pool_id):
                return pool
        return None

    def pick(self, pool_id: Optional[str]) -> Optional[str]:
        """Return the next greeting file from the pool, or None if the pool
        is missing or has no playable files (caller should fall back)."""
        pool = self.get_pool(pool_id)
        if not pool:
            if pool_id:
                self.logger.warning(f"Greeting pool {pool_id} not found")
            return None

        available = set(self.audio_controller.list_audio_files())
        files = [f for f in dict.fromkeys(pool.get('files') or []) if f in available]
        if not files:
            self.logger.warning(f"Greeting pool '{pool.get('name')}' has no playable files")
            return None

        key = str(pool_id)
        with self._lock:
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
            self._last[key] = choice

        self.logger.info(f"Greeting pool '{pool.get('name')}' picked {choice}")
        return choice
