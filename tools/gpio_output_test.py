#!/usr/bin/env python3
"""
Universal GPIO Output Test Script
================================
Lets you enter any GPIO pin number, then toggles it HIGH/LOW every 5 seconds.
Use a multimeter to check voltage between the pin and GND.
"""
import time
import RPi.GPIO as GPIO

try:
    pin = int(input("Enter the BCM GPIO pin number to test (e.g., 15): ").strip())
except Exception:
    print("Invalid input. Exiting.")
    exit(1)

print(f"Toggling GPIO {pin} HIGH/LOW every 5 seconds. Use a multimeter to check voltage.")

GPIO.setmode(GPIO.BCM)
GPIO.setup(pin, GPIO.OUT)

try:
    state = False
    while True:
        state = not state
        GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)
        print(f"GPIO {pin} is now {'HIGH' if state else 'LOW'}.")
        time.sleep(5)
except KeyboardInterrupt:
    print("\nTest ended by user.")
finally:
    GPIO.output(pin, GPIO.LOW)
    GPIO.cleanup() 