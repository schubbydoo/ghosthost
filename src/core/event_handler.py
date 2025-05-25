"""
Event Handler for Ghost Host
===========================
Coordinates sensor events with motor, audio, and LED responses.
"""

import logging
import time
from typing import Optional
from src.hardware import SensorManager, SensorType, MotorController, AudioController, LEDController

class EventHandler:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize hardware controllers
        self.motor_controller = MotorController(config)
        self.audio_controller = AudioController(config)
        self.led_controller = LEDController(config)
        
        # Initialize sensor manager with this event handler as callback
        self.sensor_manager = SensorManager(config, self.handle_event)
        
        # State tracking
        self.performance_active = False
        
        self.logger.info("Event Handler initialized")
    
    def handle_event(self, event_type: str, data):
        """Main event handler called by sensor manager"""
        if event_type == 'sensor_triggered':
            self._handle_sensor_trigger(data)
        elif event_type == 'ap_mode_requested':
            self._handle_ap_mode_request()
        else:
            self.logger.warning(f"Unknown event type: {event_type}")
    
    def _handle_sensor_trigger(self, sensor_type: SensorType):
        """Handle sensor trigger event"""
        if self.performance_active:
            self.logger.info(f"Performance already active, ignoring {sensor_type}")
            return
        
        if self.sensor_manager.is_in_cooldown():
            self.logger.info(f"In cooldown period, ignoring {sensor_type}")
            return
        
        self.logger.info(f"Starting performance for sensor: {sensor_type}")
        self._start_performance(sensor_type)
    
    def _start_performance(self, sensor_type: SensorType):
        """Start the main animatronic performance"""
        self.performance_active = True
        
        try:
            # Get audio file to play
            audio_file = self.config.get('audio.default_file', 'HMGreeting.wav')
            
            # Get audio duration
            audio_duration = self.audio_controller.get_audio_duration(audio_file)
            if not audio_duration:
                self.logger.error(f"Could not get duration for audio file: {audio_file}")
                return
            
            # Turn on eyes immediately
            self.led_controller.eyes_on_during_audio(audio_duration)
            
            # Start audio playback with completion callback
            audio_started = self.audio_controller.play_audio_file(
                audio_file, 
                self._performance_complete
            )
            
            if not audio_started:
                self.logger.error("Failed to start audio playback")
                self.led_controller.turn_off_eyes()
                self.performance_active = False
                return
            
            # Start synchronized motor movements
            self.motor_controller.start_synchronized_movement(
                audio_duration, 
                audio_file, 
                sensor_type.value
            )
            
            self.logger.info(f"Performance started - Duration: {audio_duration:.1f}s")
            
        except Exception as e:
            self.logger.error(f"Error starting performance: {e}")
            self.performance_active = False
            self._cleanup_performance()
    
    def _performance_complete(self):
        """Called when audio playback completes"""
        self.logger.info("Performance completed")
        self.performance_active = False
        
        # Start cooldown period
        self.sensor_manager.start_cooldown()
        
        # Ensure everything is stopped
        self._cleanup_performance()
    
    def _cleanup_performance(self):
        """Clean up after performance"""
        try:
            # Stop all motors
            self.motor_controller.stop_all_motors()
            
            # Turn off eyes (if not already handled by timer)
            self.led_controller.turn_off_eyes()
            
        except Exception as e:
            self.logger.error(f"Error during performance cleanup: {e}")
    
    def _handle_ap_mode_request(self):
        """Handle request to enter AP mode"""
        self.logger.info("AP mode requested via button hold")
        
        # Stop any active performance
        if self.performance_active:
            self.stop_performance()
        
        # Signal eyes that we're entering AP mode
        self.led_controller.blink_eyes(5.0, 0.3)
        
        # TODO: Implement network manager AP mode activation
        # For now, just log the request
        self.logger.info("AP mode activation would happen here")
    
    def stop_performance(self):
        """Force stop current performance"""
        if self.performance_active:
            self.logger.info("Force stopping performance")
            
            self.performance_active = False
            self.audio_controller.stop_audio()
            self._cleanup_performance()
    
    def force_end_cooldown(self):
        """Force end the current cooldown period"""
        self.sensor_manager.force_end_cooldown()
        self.logger.info("Cooldown period force ended")
    
    def trigger_test_performance(self):
        """Trigger a test performance manually"""
        if self.performance_active:
            self.logger.warning("Performance already active, cannot start test")
            return False
        
        if self.sensor_manager.is_in_cooldown():
            self.logger.warning("In cooldown period, cannot start test")
            return False
        
        self.logger.info("Starting test performance")
        self._start_performance(SensorType.BUTTON)  # Use button type for test
        return True
    
    def get_system_status(self) -> dict:
        """Get comprehensive system status"""
        return {
            'performance_active': self.performance_active,
            'sensor_status': self.sensor_manager.get_sensor_status(),
            'motor_status': self.motor_controller.get_motor_status(),
            'audio_status': self.audio_controller.get_status(),
            'led_status': self.led_controller.get_status(),
            'cooldown_active': self.sensor_manager.is_in_cooldown()
        }
    
    def cleanup(self):
        """Clean up event handler and all controllers"""
        self.logger.info("Cleaning up Event Handler")
        
        # Stop any active performance
        if self.performance_active:
            self.stop_performance()
        
        # Clean up all controllers
        try:
            self.sensor_manager.cleanup()
            self.motor_controller.cleanup()
            self.led_controller.cleanup()
            # Note: audio controller doesn't need GPIO cleanup
            
        except Exception as e:
            self.logger.error(f"Error during event handler cleanup: {e}")
        
        self.logger.info("Event Handler cleanup complete") 