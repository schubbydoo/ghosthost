#!/usr/bin/env python3
"""
Minimal LED Test Script for Ghost Host
=====================================
Blinks the LED on the configured pin 3 times.
"""
import time
import RPi.GPIO as GPIO
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from core.config_manager import config

gpio_pin = config.get_gpio_pins().get('led_eyes')

print(f"Testing LED on GPIO pin {gpio_pin}...")

GPIO.setmode(GPIO.BCM)
GPIO.setup(gpio_pin, GPIO.OUT)

try:
    for i in range(3):
        print(f"Blink {i+1} ON")
        GPIO.output(gpio_pin, GPIO.HIGH)
        time.sleep(0.5)
        print(f"Blink {i+1} OFF")
        GPIO.output(gpio_pin, GPIO.LOW)
        time.sleep(0.5)
    print("LED test complete. LED should be OFF now.")
finally:
    GPIO.output(gpio_pin, GPIO.LOW)
    GPIO.cleanup() 