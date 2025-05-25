"""
Sensor Manager for Ghost Host
============================
Handles PIR sensors, button, and pressure pad with debouncing and event detection.
"""

import RPi.GPIO as GPIO
import time
import threading
import logging
from typing import Callable, Optional
from enum import Enum

class SensorType(Enum):
    SENSOR_PORT_LEFT = "sensor_port_left"
    SENSOR_PORT_RIGHT = "sensor_port_right"

class SensorManager:
    def __init__(self, config, event_callback: Optional[Callable] = None):
        self.config = config
        self.gpio_pins = config.get_gpio_pins()
        self.sensor_settings = config.get_sensor_settings()
        self.event_callback = event_callback
        self.logger = logging.getLogger(__name__)
        
        # State tracking
        self.last_trigger_time = {}
        self.in_cooldown = False
        self.cooldown_end_time = 0
        
        # Button hold detection for AP mode
        self.button_press_start = None
        self.ap_mode_threshold = 10.0  # 10 seconds
        
        self.setup_gpio()
        self.logger.info("Sensor Manager initialized")
    
    def setup_gpio(self):
        """Initialize GPIO pins for sensors and start polling thread"""
        GPIO.setmode(GPIO.BCM)
        sensor_pins = ['sensor_port_left', 'sensor_port_right']
        for pin_name in sensor_pins:
            pin = self.gpio_pins.get(pin_name)
            if pin:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                self.last_trigger_time[pin_name] = 0
        self.logger.info("GPIO configured for sensors (polling mode)")
        self._last_pin_state = {name: 0 for name in sensor_pins}
        self._polling = True
        self._poll_thread = threading.Thread(target=self._poll_sensors, daemon=True)
        self._poll_thread.start()

    def _poll_sensors(self):
        """Background thread to poll sensor pins and detect rising edges"""
        poll_interval = self.sensor_settings.get('poll_interval', 0.02)  # 20ms default
        sensor_pins = ['sensor_port_left', 'sensor_port_right']
        while self._polling:
            for pin_name in sensor_pins:
                pin = self.gpio_pins.get(pin_name)
                if not pin:
                    continue
                state = GPIO.input(pin)
                last_state = self._last_pin_state.get(pin_name, 0)
                # Detect rising edge (LOW to HIGH)
                if last_state == 0 and state == 1:
                    self._sensor_triggered(pin_name)
                self._last_pin_state[pin_name] = state
            time.sleep(poll_interval)
    
    def _sensor_triggered(self, sensor_name: str):
        """Handle sensor trigger with debouncing and cooldown logic"""
        current_time = time.time()
        
        # Check if we're in cooldown period
        if self.in_cooldown and current_time < self.cooldown_end_time:
            self.logger.debug(f"Sensor {sensor_name} triggered during cooldown, ignoring")
            return
        
        # Additional debouncing check
        last_trigger = self.last_trigger_time.get(sensor_name, 0)
        debounce_time = self.sensor_settings.get('debounce_time', 0.2)
        
        if current_time - last_trigger < debounce_time:
            self.logger.debug(f"Sensor {sensor_name} debounce, ignoring")
            return
        
        # Update last trigger time
        self.last_trigger_time[sensor_name] = current_time
        
        # All sensors are treated the same now
        self._trigger_event(sensor_name)
    
    def _trigger_event(self, sensor_name: str):
        """Trigger the main event and start cooldown"""
        self.logger.info(f"Sensor triggered: {sensor_name}")
        
        # Map sensor name to sensor type
        sensor_type_map = {
            'sensor_port_left': SensorType.SENSOR_PORT_LEFT,
            'sensor_port_right': SensorType.SENSOR_PORT_RIGHT
        }
        
        sensor_type = sensor_type_map.get(sensor_name)
        
        if self.event_callback and sensor_type:
            self.event_callback('sensor_triggered', sensor_type)
    
    def start_cooldown(self):
        """Start the cooldown period after audio playback"""
        cooldown_duration = self.sensor_settings.get('cooldown_period', 30)
        self.cooldown_end_time = time.time() + cooldown_duration
        self.in_cooldown = True
        
        self.logger.info(f"Cooldown started for {cooldown_duration} seconds")
        
        # Start a thread to end cooldown
        threading.Thread(
            target=self._end_cooldown_timer,
            args=(cooldown_duration,),
            daemon=True
        ).start()
    
    def _end_cooldown_timer(self, duration: float):
        """End cooldown after specified duration"""
        time.sleep(duration)
        self.in_cooldown = False
        self.logger.info("Cooldown period ended")
    
    def is_in_cooldown(self) -> bool:
        """Check if currently in cooldown period"""
        if self.in_cooldown and time.time() >= self.cooldown_end_time:
            self.in_cooldown = False
        return self.in_cooldown
    
    def force_end_cooldown(self):
        """Force end the cooldown period"""
        self.in_cooldown = False
        self.cooldown_end_time = 0
        self.logger.info("Cooldown period force ended")
    
    def get_sensor_status(self) -> dict:
        """Get current status of all sensors"""
        status = {}
        
        for sensor_name, pin in self.gpio_pins.items():
            if sensor_name in ['sensor_port_left', 'sensor_port_right']:
                try:
                    # Read current state (active HIGH)
                    state = GPIO.input(pin)
                    status[sensor_name] = {
                        'active': bool(state),
                        'pin': pin,
                        'last_trigger': self.last_trigger_time.get(sensor_name, 0)
                    }
                except Exception as e:
                    status[sensor_name] = {
                        'active': False,
                        'pin': pin,
                        'error': str(e)
                    }
        
        status['cooldown'] = {
            'active': self.in_cooldown,
            'end_time': self.cooldown_end_time
        }
        
        return status
    
    def cleanup(self):
        """Clean up GPIO and stop polling"""
        try:
            self._polling = False
            GPIO.cleanup()
            self.logger.info("Sensor Manager cleaned up")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}") 