#!/usr/bin/env python3
"""
Idle Look-Around Script for Ghost Host
Periodically moves head/torso/eyes for idle behavior, unless main process is busy.
"""
import time
import os
import logging
from pathlib import Path
import sys
import signal

import RPi.GPIO as GPIO

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config_manager import config

LOCK_FILE = '/tmp/ghosthost_busy.lock'
LOGFILE = '/home/ghosthost/logs/look_around.log'

# GPIO pin assignments (from config/PRD)
PINS = config.get_gpio_pins()
EYES = PINS.get('led_eyes', 15)
HEAD_IN1 = PINS.get('motor_head_in1', 4)
HEAD_IN2 = PINS.get('motor_head_in2', 14)
TORSO_IN1 = PINS.get('motor_torso_in1', 17)
TORSO_IN2 = PINS.get('motor_torso_in2', 18)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGFILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("look_around")

def is_busy():
    return os.path.exists(LOCK_FILE)

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pin in [EYES, HEAD_IN1, HEAD_IN2, TORSO_IN1, TORSO_IN2]:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

def cleanup_gpio():
    GPIO.output(EYES, GPIO.LOW)
    GPIO.output(HEAD_IN1, GPIO.LOW)
    GPIO.output(HEAD_IN2, GPIO.LOW)
    GPIO.output(TORSO_IN1, GPIO.LOW)
    GPIO.output(TORSO_IN2, GPIO.LOW)
    GPIO.cleanup()
    logger.info("GPIO cleaned up.")

def move_head_torso_eyes(duration, direction):
    logger.info(f"Moving head/torso/eyes for {duration} seconds (idle look-around, direction: {direction})")
    # Eyes ON
    GPIO.output(EYES, GPIO.HIGH)
    # Head movement
    if direction == 'right':
        GPIO.output(HEAD_IN1, GPIO.HIGH)
        GPIO.output(HEAD_IN2, GPIO.LOW)
    else:  # left
        GPIO.output(HEAD_IN1, GPIO.LOW)
        GPIO.output(HEAD_IN2, GPIO.HIGH)
    # Torso movement
    if direction == 'right':
        GPIO.output(TORSO_IN1, GPIO.HIGH)
        GPIO.output(TORSO_IN2, GPIO.LOW)
    else:  # left
        GPIO.output(TORSO_IN1, GPIO.LOW)
        GPIO.output(TORSO_IN2, GPIO.HIGH)
    t0 = time.time()
    interrupted = False
    while time.time() - t0 < duration:
        if is_busy():
            logger.info("Main process became busy during look-around. Stopping movement.")
            interrupted = True
            break
        time.sleep(0.1)
    # Stop all movement
    GPIO.output(HEAD_IN1, GPIO.LOW)
    GPIO.output(HEAD_IN2, GPIO.LOW)
    GPIO.output(TORSO_IN1, GPIO.LOW)
    GPIO.output(TORSO_IN2, GPIO.LOW)
    GPIO.output(EYES, GPIO.LOW)
    logger.info("Stopped head/torso/eyes movement (idle look-around)")
    return interrupted

def main():
    logger.info("Idle look-around script started.")
    setup_gpio()
    direction = 'right'
    def handle_exit(signum, frame):
        logger.info(f"Received signal {signum}, cleaning up GPIO and exiting.")
        cleanup_gpio()
        sys.exit(0)
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    try:
        while True:
            settings = config.get_idle_behavior_settings()
            enabled = settings.get('enabled', False)
            interval = settings.get('interval_seconds', 120)
            duration = settings.get('duration_seconds', 5)
            if not enabled:
                logger.info("Idle look-around is disabled. Sleeping 30s.")
                time.sleep(30)
                continue
            # Wait for interval, checking for busy
            logger.info(f"Waiting {interval} seconds before next look-around.")
            t0 = time.time()
            while time.time() - t0 < interval:
                if is_busy():
                    logger.info("Main process busy during idle wait. Pausing idle behavior.")
                    time.sleep(1)
                    t0 = time.time()  # Reset interval after busy
                else:
                    time.sleep(1)
            # Check again before moving
            if is_busy():
                logger.info("Main process busy at start of look-around. Skipping this cycle.")
                continue
            interrupted = move_head_torso_eyes(duration, direction)
            # Alternate direction for next cycle
            direction = 'left' if direction == 'right' else 'right'
    finally:
        cleanup_gpio()

if __name__ == "__main__":
    main() 