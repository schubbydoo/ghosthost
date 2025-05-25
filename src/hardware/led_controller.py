"""
LED Controller for Ghost Host
============================
Controls LED eyes with simple on/off functionality.
"""

import RPi.GPIO as GPIO
import time
import threading
import logging
from typing import Optional

class LEDController:
    def __init__(self, config):
        self.config = config
        self.gpio_pins = config.get_gpio_pins()
        self.logger = logging.getLogger(__name__)
        
        # LED state tracking
        self.eyes_on = False
        self.blink_thread = None
        self.stop_blink = False
        
        self.setup_gpio()
        self.logger.info("LED Controller initialized")
    
    def setup_gpio(self):
        """Initialize GPIO pin for LED control"""
        GPIO.setmode(GPIO.BCM)
        
        led_pin = self.gpio_pins.get('led_eyes')
        if led_pin:
            GPIO.setup(led_pin, GPIO.OUT)
            GPIO.output(led_pin, GPIO.LOW)  # Start with eyes off
        
        self.logger.info("GPIO configured for LEDs")
    
    def turn_on_eyes(self):
        """Turn on LED eyes"""
        led_pin = self.gpio_pins.get('led_eyes')
        if led_pin:
            GPIO.output(led_pin, GPIO.HIGH)
            self.eyes_on = True
            self.logger.info("Eyes turned on")
    
    def turn_off_eyes(self):
        """Turn off LED eyes"""
        led_pin = self.gpio_pins.get('led_eyes')
        if led_pin:
            GPIO.output(led_pin, GPIO.LOW)
            self.eyes_on = False
            self.logger.info("Eyes turned off")
    
    def toggle_eyes(self):
        """Toggle LED eyes on/off"""
        if self.eyes_on:
            self.turn_off_eyes()
        else:
            self.turn_on_eyes()
    
    def blink_eyes(self, duration: float = 5.0, blink_interval: float = 0.5):
        """Blink eyes for specified duration"""
        if self.blink_thread and self.blink_thread.is_alive():
            self.stop_blinking()
        
        self.stop_blink = False
        self.blink_thread = threading.Thread(
            target=self._blink_worker,
            args=(duration, blink_interval),
            daemon=True
        )
        self.blink_thread.start()
        
        self.logger.info(f"Started blinking eyes for {duration} seconds")
    
    def _blink_worker(self, duration: float, blink_interval: float):
        """Worker thread for eye blinking"""
        end_time = time.time() + duration
        
        while time.time() < end_time and not self.stop_blink:
            self.turn_on_eyes()
            time.sleep(blink_interval / 2)
            
            if self.stop_blink:
                break
                
            self.turn_off_eyes()
            time.sleep(blink_interval / 2)
        
        # Ensure eyes are on at the end
        if not self.stop_blink:
            self.turn_on_eyes()
        
        self.logger.info("Eye blinking completed")
    
    def stop_blinking(self):
        """Stop eye blinking"""
        self.stop_blink = True
        if self.blink_thread and self.blink_thread.is_alive():
            self.blink_thread.join(timeout=1.0)
        self.logger.info("Eye blinking stopped")
    
    def flash_eyes(self, flash_count: int = 3, flash_speed: float = 0.1):
        """Quick flash eyes specified number of times"""
        self.logger.info(f"Flashing eyes {flash_count} times")
        
        for i in range(flash_count):
            self.turn_on_eyes()
            time.sleep(flash_speed)
            self.turn_off_eyes()
            time.sleep(flash_speed)
        
        # Turn eyes back on after flashing
        self.turn_on_eyes()
    
    def eyes_on_during_audio(self, audio_duration: float):
        """Turn eyes on for the duration of audio playback"""
        self.turn_on_eyes()
        
        # Start a thread to turn off eyes after audio ends
        threading.Thread(
            target=self._turn_off_after_delay,
            args=(audio_duration,),
            daemon=True
        ).start()
        
        self.logger.info(f"Eyes will be on for {audio_duration} seconds during audio")
    
    def _turn_off_after_delay(self, delay: float):
        """Turn off eyes after specified delay"""
        time.sleep(delay)
        self.turn_off_eyes()
    
    def get_status(self) -> dict:
        """Get current LED status"""
        return {
            'eyes_on': self.eyes_on,
            'blinking': self.blink_thread and self.blink_thread.is_alive(),
            'led_pin': self.gpio_pins.get('led_eyes')
        }
    
    def test_eyes(self, test_duration: float = 2.0):
        """Test LED eyes functionality"""
        self.logger.info(f"Testing eyes for {test_duration} seconds")
        
        # Flash a few times
        self.flash_eyes(3, 0.2)
        
        # Stay on for remaining time
        remaining_time = test_duration - 1.2  # Account for flash time
        if remaining_time > 0:
            time.sleep(remaining_time)
        
        # Turn off at the end
        self.turn_off_eyes()
        
        self.logger.info("Eye test completed")
    
    def cleanup(self):
        """Clean up LED controller"""
        self.stop_blinking()
        self.turn_off_eyes()
        
        try:
            GPIO.cleanup()
            self.logger.info("LED Controller cleaned up")
        except Exception as e:
            self.logger.error(f"Error during LED cleanup: {e}") 