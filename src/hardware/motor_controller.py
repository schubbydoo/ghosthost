"""
Motor Controller for Ghost Host
==============================
Controls head, torso, and mouth motors with synchronized movements during audio playback.
"""

import RPi.GPIO as GPIO
import time
import threading
import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any

class MotorController:
    def __init__(self, config):
        self.config = config
        self.gpio_pins = config.get_gpio_pins()
        self.motor_settings = config.get_motor_settings()
        self.logger = logging.getLogger(__name__)
        
        # Motor state tracking
        self.motors_running = False
        self.mouth_thread = None
        self.head_torso_thread = None
        
        self.setup_gpio()
        self.logger.info("Motor Controller initialized")
    
    def setup_gpio(self):
        """Initialize GPIO pins for motor control"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
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
        
        self.logger.info("GPIO configured for motors")
    
    def start_synchronized_movement(self, audio_duration: float, audio_file: str, sensor_type: str = None):
        """Start synchronized motor movements with audio playback"""
        if self.motors_running:
            self.logger.warning("Motors already running, ignoring new request")
            return
        
        self.motors_running = True
        self.logger.info(f"Starting synchronized movement for {audio_duration} seconds")
        
        # Get timestamps for mouth movement
        timestamps = self._load_audio_timestamps(audio_file)
        
        # Start mouth movement thread
        if timestamps:
            self.mouth_thread = threading.Thread(
                target=self._animate_mouth,
                args=(timestamps,),
                daemon=True
            )
            self.mouth_thread.start()
        
        # Start head/torso movement thread
        head_torso_duration = self.motor_settings.get('head_torso_duration', 0)
        if head_torso_duration == 0:
            head_torso_duration = audio_duration  # Run for full audio duration
        
        self.head_torso_thread = threading.Thread(
            target=self._animate_head_torso,
            args=(head_torso_duration, sensor_type),
            daemon=True
        )
        self.head_torso_thread.start()
        
        # Start a thread to stop motors after audio ends
        threading.Thread(
            target=self._stop_motors_after_delay,
            args=(audio_duration,),
            daemon=True
        ).start()
    
    def _load_audio_timestamps(self, audio_file: str) -> Optional[list]:
        """Load word timestamps for mouth animation"""
        try:
            soundfiles_dir = self.config.get('audio.soundfiles_dir', 'SoundFiles')
            timestamp_file = audio_file.replace('.wav', '_timestamps.json')
            timestamp_path = Path(soundfiles_dir) / timestamp_file
            
            if timestamp_path.exists():
                with open(timestamp_path, 'r') as f:
                    return json.load(f)
            else:
                self.logger.warning(f"Timestamp file not found: {timestamp_path}")
                return None
        except Exception as e:
            self.logger.error(f"Error loading timestamps: {e}")
            return None
    
    def _animate_mouth(self, timestamps: list):
        """Animate mouth based on word timestamps"""
        start_time = time.time()
        mouth_open_duration = self.motor_settings.get('mouth_open_duration', 0.1)
        mouth_close_delay = self.motor_settings.get('mouth_close_delay', 0.05)
        
        for word in timestamps:
            if not self.motors_running:
                break
                
            word_start = word['start']
            word_end = word['end']
            current_time = time.time() - start_time
            
            # Wait until word start time
            sleep_time = word_start - current_time
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            if not self.motors_running:
                break
            
            # Open mouth
            self._mouth_open()
            
            # Keep mouth open for word duration or minimum duration
            word_duration = word_end - word_start
            mouth_duration = max(word_duration, mouth_open_duration)
            time.sleep(mouth_duration)
            
            # Close mouth
            self._mouth_close()
            
            # Brief pause between words
            time.sleep(mouth_close_delay)
        
        # Ensure mouth is closed at the end
        self._mouth_close()
    
    def _animate_head_torso(self, duration: float, sensor_type: str = None):
        """Animate head and torso movements"""
        # For now, just run motors in one direction for the duration
        # Future enhancement: vary direction based on sensor_type
        
        self.logger.info(f"Starting head/torso movement for {duration} seconds")
        
        # Start head motor (left rotation)
        GPIO.output(self.gpio_pins['motor_head_in1'], GPIO.HIGH)
        GPIO.output(self.gpio_pins['motor_head_in2'], GPIO.LOW)
        
        # Start torso motor (left rotation)
        GPIO.output(self.gpio_pins['motor_torso_in1'], GPIO.HIGH)
        GPIO.output(self.gpio_pins['motor_torso_in2'], GPIO.LOW)
        
        # Run for specified duration
        time.sleep(duration)
        
        # Stop motors
        self._stop_head_torso_motors()
    
    def _mouth_open(self):
        """Open mouth motor"""
        GPIO.output(self.gpio_pins['motor_mouth_in1'], GPIO.HIGH)
        GPIO.output(self.gpio_pins['motor_mouth_in2'], GPIO.LOW)
    
    def _mouth_close(self):
        """Close mouth motor (stop - spring return)"""
        GPIO.output(self.gpio_pins['motor_mouth_in1'], GPIO.LOW)
        GPIO.output(self.gpio_pins['motor_mouth_in2'], GPIO.LOW)
    
    def _stop_head_torso_motors(self):
        """Stop head and torso motors"""
        GPIO.output(self.gpio_pins['motor_head_in1'], GPIO.LOW)
        GPIO.output(self.gpio_pins['motor_head_in2'], GPIO.LOW)
        GPIO.output(self.gpio_pins['motor_torso_in1'], GPIO.LOW)
        GPIO.output(self.gpio_pins['motor_torso_in2'], GPIO.LOW)
    
    def _stop_motors_after_delay(self, delay: float):
        """Stop all motors after specified delay"""
        time.sleep(delay)
        self.stop_all_motors()
    
    def stop_all_motors(self):
        """Stop all motors immediately"""
        self.motors_running = False
        
        # Stop all motor outputs
        self._mouth_close()
        self._stop_head_torso_motors()
        
        self.logger.info("All motors stopped")
    
    def test_motor(self, motor_type: str, duration: float = 1.0, direction: str = "forward"):
        """Test individual motor for specified duration"""
        if self.motors_running:
            self.logger.warning("Cannot test motor while motors are running")
            return False
        
        self.logger.info(f"Testing {motor_type} motor for {duration} seconds")
        
        try:
            if motor_type == "mouth":
                self._mouth_open()
                time.sleep(duration)
                self._mouth_close()
                
            elif motor_type == "head":
                if direction == "forward":
                    GPIO.output(self.gpio_pins['motor_head_in1'], GPIO.HIGH)
                    GPIO.output(self.gpio_pins['motor_head_in2'], GPIO.LOW)
                else:
                    GPIO.output(self.gpio_pins['motor_head_in1'], GPIO.LOW)
                    GPIO.output(self.gpio_pins['motor_head_in2'], GPIO.HIGH)
                
                time.sleep(duration)
                
                GPIO.output(self.gpio_pins['motor_head_in1'], GPIO.LOW)
                GPIO.output(self.gpio_pins['motor_head_in2'], GPIO.LOW)
                
            elif motor_type == "torso":
                if direction == "forward":
                    GPIO.output(self.gpio_pins['motor_torso_in1'], GPIO.HIGH)
                    GPIO.output(self.gpio_pins['motor_torso_in2'], GPIO.LOW)
                else:
                    GPIO.output(self.gpio_pins['motor_torso_in1'], GPIO.LOW)
                    GPIO.output(self.gpio_pins['motor_torso_in2'], GPIO.HIGH)
                
                time.sleep(duration)
                
                GPIO.output(self.gpio_pins['motor_torso_in1'], GPIO.LOW)
                GPIO.output(self.gpio_pins['motor_torso_in2'], GPIO.LOW)
            
            else:
                self.logger.error(f"Unknown motor type: {motor_type}")
                return False
            
            self.logger.info(f"{motor_type} motor test completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error testing {motor_type} motor: {e}")
            return False
    
    def get_motor_status(self) -> Dict[str, Any]:
        """Get current motor status"""
        return {
            'motors_running': self.motors_running,
            'mouth_active': self.mouth_thread and self.mouth_thread.is_alive(),
            'head_torso_active': self.head_torso_thread and self.head_torso_thread.is_alive(),
            'settings': self.motor_settings
        }
    
    def cleanup(self):
        """Clean up motor controller"""
        self.stop_all_motors()
        time.sleep(0.1)  # Brief delay to ensure motors stop
        
        try:
            GPIO.cleanup()
            self.logger.info("Motor Controller cleaned up")
        except Exception as e:
            self.logger.error(f"Error during motor cleanup: {e}") 