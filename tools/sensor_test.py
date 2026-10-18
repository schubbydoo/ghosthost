#!/usr/bin/env python3
"""Watch both sensor ports and print every level change.

Wave your hand in front of the PIR; the port it is wired to will flip.
Run on the Pi:  python3 tools/sensor_test.py   (Ctrl+C to stop)
"""
import os
import sys
import time

import RPi.GPIO as GPIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.core.config_manager import ConfigManager

pins = ConfigManager().get_gpio_pins()
ports = {name: pins[name] for name in ('sensor_port_left', 'sensor_port_right')}

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
# Same pulls the real service uses
GPIO.setup(ports['sensor_port_left'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(ports['sensor_port_right'], GPIO.IN, pull_up_down=GPIO.PUD_UP)

last = {n: GPIO.input(p) for n, p in ports.items()}
print("Initial levels: " + ", ".join(f"{n} (GPIO{p})={last[n]}" for n, p in ports.items()))
print("Wave at the PIR... (Ctrl+C to stop)")
try:
    while True:
        for name, pin in ports.items():
            level = GPIO.input(pin)
            if level != last[name]:
                print(f"{time.strftime('%H:%M:%S')}  {name} (GPIO{pin}): {last[name]} -> {level}")
                last[name] = level
        time.sleep(0.02)
except KeyboardInterrupt:
    pass
finally:
    GPIO.cleanup()
