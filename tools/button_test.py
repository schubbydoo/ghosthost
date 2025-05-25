#!/usr/bin/env python3
"""
Button Test Script for Ghost Host
================================
Prompts user to press the button and reports when detected.
"""
import time
import RPi.GPIO as GPIO
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from core.config_manager import config

# Prompt user for which port to test
ports = config.get_gpio_pins()
port_options = {
    'left': ports.get('sensor_port_left'),
    'right': ports.get('sensor_port_right')
}

print("Which sensor port do you want to test for a button press?")
for name, pin in port_options.items():
    print(f"  {name}: GPIO {pin}")

choice = input("Enter 'left' or 'right': ").strip().lower()
if choice not in port_options or port_options[choice] is None:
    print("Invalid choice or pin not configured.")
    sys.exit(1)

gpio_pin = port_options[choice]
print(f"Testing button on GPIO pin {gpio_pin} ({choice})...")

GPIO.setmode(GPIO.BCM)
GPIO.setup(gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

try:
    print("Please press and release the button...")
    while True:
        state = GPIO.input(gpio_pin)
        print(f"GPIO {gpio_pin} state: {'HIGH (pressed)' if state == GPIO.HIGH else 'LOW (not pressed)'}", end='\r')
        if state == GPIO.HIGH:
            print(f"\nButton pressed!")
            while GPIO.input(gpio_pin) == GPIO.HIGH:
                time.sleep(0.05)  # Wait for release
            print("Button released!")
            break
        time.sleep(0.05)
    print("Button test complete.")
finally:
    GPIO.cleanup() 