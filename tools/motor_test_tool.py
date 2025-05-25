#!/usr/bin/env python3
"""
Motor Testing Tool for Ghost Host
=================================
Interactive tool to test motor movements and determine optimal durations.
Use this to find the right timing for mouth, head, and torso movements.
"""

import sys
import os
import time
import RPi.GPIO as GPIO
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config_manager import config

class MotorTester:
    def __init__(self):
        self.gpio_pins = config.get_gpio_pins()
        self.setup_gpio()
        
    def setup_gpio(self):
        """Initialize GPIO pins for motor control"""
        GPIO.setmode(GPIO.BCM)
        
        # Setup motor pins as outputs
        motor_pins = [
            'motor_head_in1', 'motor_head_in2',
            'motor_torso_in1', 'motor_torso_in2', 
            'motor_mouth_in1', 'motor_mouth_in2'
        ]
        
        for pin_name in motor_pins:
            pin = self.gpio_pins.get(pin_name)
            if pin:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)
        
        print("GPIO initialized for motor testing")
    
    def cleanup(self):
        """Clean up GPIO"""
        GPIO.cleanup()
        print("GPIO cleaned up")
    
    def test_mouth_motor(self, duration=0.1):
        """Test mouth motor for specified duration"""
        print(f"Testing mouth motor for {duration} seconds...")
        
        # Open mouth
        GPIO.output(self.gpio_pins['motor_mouth_in1'], GPIO.HIGH)
        GPIO.output(self.gpio_pins['motor_mouth_in2'], GPIO.LOW)
        time.sleep(duration)
        
        # Stop motor (spring returns to closed)
        GPIO.output(self.gpio_pins['motor_mouth_in1'], GPIO.LOW)
        GPIO.output(self.gpio_pins['motor_mouth_in2'], GPIO.LOW)
        
        print("Mouth motor test complete")
    
    def test_head_motor(self, duration=1.0, direction="left"):
        """Test head motor rotation"""
        print(f"Testing head motor - {direction} rotation for {duration} seconds...")
        
        if direction == "left":
            GPIO.output(self.gpio_pins['motor_head_in1'], GPIO.HIGH)
            GPIO.output(self.gpio_pins['motor_head_in2'], GPIO.LOW)
        else:  # right
            GPIO.output(self.gpio_pins['motor_head_in1'], GPIO.LOW)
            GPIO.output(self.gpio_pins['motor_head_in2'], GPIO.HIGH)
        
        time.sleep(duration)
        
        # Stop motor
        GPIO.output(self.gpio_pins['motor_head_in1'], GPIO.LOW)
        GPIO.output(self.gpio_pins['motor_head_in2'], GPIO.LOW)
        
        print("Head motor test complete")
    
    def test_torso_motor(self, duration=1.0, direction="left"):
        """Test torso motor rotation"""
        print(f"Testing torso motor - {direction} rotation for {duration} seconds...")
        
        if direction == "left":
            GPIO.output(self.gpio_pins['motor_torso_in1'], GPIO.HIGH)
            GPIO.output(self.gpio_pins['motor_torso_in2'], GPIO.LOW)
        else:  # right
            GPIO.output(self.gpio_pins['motor_torso_in1'], GPIO.LOW)
            GPIO.output(self.gpio_pins['motor_torso_in2'], GPIO.HIGH)
        
        time.sleep(duration)
        
        # Stop motor
        GPIO.output(self.gpio_pins['motor_torso_in1'], GPIO.LOW)
        GPIO.output(self.gpio_pins['motor_torso_in2'], GPIO.LOW)
        
        print("Torso motor test complete")
    
    def full_rotation_test(self, motor_type="head", total_time=10.0):
        """Test how long it takes for a full 180-degree rotation"""
        print(f"Testing {motor_type} motor full rotation for {total_time} seconds...")
        print("Watch the movement and note when it completes 180 degrees")
        
        if motor_type == "head":
            GPIO.output(self.gpio_pins['motor_head_in1'], GPIO.HIGH)
            GPIO.output(self.gpio_pins['motor_head_in2'], GPIO.LOW)
        elif motor_type == "torso":
            GPIO.output(self.gpio_pins['motor_torso_in1'], GPIO.HIGH)
            GPIO.output(self.gpio_pins['motor_torso_in2'], GPIO.LOW)
        
        time.sleep(total_time)
        
        # Stop motor
        if motor_type == "head":
            GPIO.output(self.gpio_pins['motor_head_in1'], GPIO.LOW)
            GPIO.output(self.gpio_pins['motor_head_in2'], GPIO.LOW)
        elif motor_type == "torso":
            GPIO.output(self.gpio_pins['motor_torso_in1'], GPIO.LOW)
            GPIO.output(self.gpio_pins['motor_torso_in2'], GPIO.LOW)
        
        print(f"{motor_type.capitalize()} full rotation test complete")

def main():
    tester = MotorTester()
    
    try:
        while True:
            print("\n" + "="*50)
            print("Ghost Host Motor Testing Tool")
            print("="*50)
            print("1. Test mouth motor (quick open/close)")
            print("2. Test head motor rotation")
            print("3. Test torso motor rotation") 
            print("4. Full rotation timing test")
            print("5. Custom mouth duration test")
            print("6. Exit")
            print("-"*50)
            
            choice = input("Enter your choice (1-6): ").strip()
            
            if choice == "1":
                tester.test_mouth_motor()
                
            elif choice == "2":
                direction = input("Direction (left/right) [left]: ").strip() or "left"
                duration = float(input("Duration in seconds [1.0]: ") or "1.0")
                tester.test_head_motor(duration, direction)
                
            elif choice == "3":
                direction = input("Direction (left/right) [left]: ").strip() or "left"
                duration = float(input("Duration in seconds [1.0]: ") or "1.0")
                tester.test_torso_motor(duration, direction)
                
            elif choice == "4":
                motor = input("Motor to test (head/torso) [head]: ").strip() or "head"
                duration = float(input("Test duration in seconds [10.0]: ") or "10.0")
                tester.full_rotation_test(motor, duration)
                
            elif choice == "5":
                duration = float(input("Mouth open duration in seconds [0.1]: ") or "0.1")
                tester.test_mouth_motor(duration)
                
            elif choice == "6":
                break
                
            else:
                print("Invalid choice, please try again")
                
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        tester.cleanup()

if __name__ == "__main__":
    main() 