#!/usr/bin/env python3
"""
Ghost Host System Test
=====================
Test script to verify all system components are working correctly.
"""

import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config_manager import config
from src.hardware import SensorManager, MotorController, AudioController, LEDController

def test_configuration():
    """Test configuration loading"""
    print("Testing configuration...")
    
    # Test config access
    gpio_pins = config.get_gpio_pins()
    audio_settings = config.get_audio_settings()
    
    print(f"  ✓ GPIO pins loaded: {len(gpio_pins)} pins configured")
    print(f"  ✓ Audio settings: {audio_settings.get('default_file', 'None')}")
    print("  ✓ Configuration test passed\n")

def test_led_controller():
    """Test LED controller"""
    print("Testing LED controller...")
    
    try:
        led = LEDController(config)
        
        print("  - Flashing eyes 3 times...")
        led.flash_eyes(3, 0.3)
        
        print("  - Testing eye toggle...")
        led.turn_on_eyes()
        time.sleep(1)
        led.turn_off_eyes()
        
        led.cleanup()
        print("  ✓ LED controller test passed\n")
        
    except Exception as e:
        print(f"  ✗ LED controller test failed: {e}\n")

def test_audio_controller():
    """Test audio controller"""
    print("Testing audio controller...")
    
    try:
        audio = AudioController(config)
        
        # Test volume control
        current_volume = audio.get_volume()
        print(f"  - Current volume: {current_volume}%")
        
        # Test file listing
        files = audio.list_audio_files()
        print(f"  - Available audio files: {len(files)}")
        for file in files:
            print(f"    - {file}")
        
        # Test duration calculation
        if files:
            duration = audio.get_audio_duration(files[0])
            print(f"  - Duration of {files[0]}: {duration}s")
        
        print("  ✓ Audio controller test passed\n")
        
    except Exception as e:
        print(f"  ✗ Audio controller test failed: {e}\n")

def test_motor_controller():
    """Test motor controller"""
    print("Testing motor controller...")
    
    try:
        motor = MotorController(config)
        
        print("  - Testing mouth motor (0.5s)...")
        motor.test_motor("mouth", 0.5)
        time.sleep(1)
        
        print("  - Testing head motor (1s)...")
        motor.test_motor("head", 1.0)
        time.sleep(1)
        
        print("  - Testing torso motor (1s)...")
        motor.test_motor("torso", 1.0)
        
        motor.cleanup()
        print("  ✓ Motor controller test passed\n")
        
    except Exception as e:
        print(f"  ✗ Motor controller test failed: {e}\n")

def test_sensor_manager():
    """Test sensor manager"""
    print("Testing sensor manager...")
    
    try:
        # Simple sensor manager test without event callback
        sensor = SensorManager(config)
        
        # Get sensor status
        status = sensor.get_sensor_status()
        print("  - Sensor status:")
        for sensor_name, sensor_info in status.items():
            if sensor_name != 'cooldown':
                pin = sensor_info.get('pin', 'N/A')
                active = sensor_info.get('active', False)
                print(f"    - {sensor_name}: Pin {pin}, Active: {active}")
        
        sensor.cleanup()
        print("  ✓ Sensor manager test passed\n")
        
    except Exception as e:
        print(f"  ✗ Sensor manager test failed: {e}\n")

def main():
    """Run all system tests"""
    print("="*50)
    print("Ghost Host System Test")
    print("="*50)
    print()
    
    try:
        test_configuration()
        test_led_controller()
        test_audio_controller()
        test_motor_controller()
        test_sensor_manager()
        
        print("="*50)
        print("All tests completed!")
        print("="*50)
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nUnexpected error during testing: {e}")

if __name__ == "__main__":
    main() 