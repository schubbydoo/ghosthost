"""
Event Handler for Ghost Host
===========================
Coordinates sensor events with motor, audio, and LED responses.
"""

import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional
from src.hardware import SensorManager, SensorType, MotorController, AudioController, LEDController
from src.core.greeting_pool import GreetingPicker

def _make_recorder():
    """The shared activity log (propkit). Optional: without propkit nothing is recorded and nothing else changes."""
    try:
        sys.path.append(os.environ.get("PROPKIT_DIR", os.path.join(os.path.expanduser("~"), "propkit")))
        from propkit.stats import Recorder
        return Recorder(str(Path(__file__).resolve().parent.parent.parent / "logs"))
    except Exception as e:
        logging.getLogger(__name__).warning(f"Activity recording is off: {e}")
        return None


class EventHandler:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.recorder = _make_recorder()
        self._perf = None   # the performance in progress: file, source, extra, start time
        
        # State tracking
        self.performance_active = False
        self.current_audio = None   # file being performed, for the web UI's Stop bar
        
        # Initialize hardware controllers
        self.motor_controller = MotorController(config)
        self.audio_controller = AudioController(config)
        self.led_controller = LEDController(config)
        self.greeting_picker = GreetingPicker(config, self.audio_controller)
        
        # Initialize sensor manager with this event handler as callback
        self.sensor_manager = SensorManager(config, self.handle_event)
        self.sensor_manager.start_polling()
        
        self.logger.info("Event Handler initialized")
    
    @staticmethod
    def _source_for(trigger_id):
        """Where a network-style performance came from, from the id the caller passed."""
        if trigger_id == 'live':
            return 'live'
        if str(trigger_id or '').startswith('timed:'):
            return 'timed'
        return 'network_trigger'

    def _perf_started(self, audio_file, source, **extra):
        self._perf = {'file': audio_file, 'source': source, 'extra': extra, 't0': time.time()}

    def _perf_record(self, outcome, audio_file=None, source=None, seconds=None, **extra):
        """Add one line to the activity log. Never raises: the log must not disturb a performance."""
        try:
            if not self.recorder:
                return
            p = self._perf or {}
            if seconds is None and p.get('t0'):
                seconds = time.time() - p['t0']
            merged = dict(p.get('extra') or {}, **extra)
            self.recorder.record('play', outcome, seconds=seconds, detail=audio_file or p.get('file'),
                                 source=source or p.get('source'), **merged)
        except Exception:
            pass

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
    
    def _sensor_audio_file(self, sensor_type: SensorType) -> str:
        """Greeting for a sensor: random pick from its assigned pool, else the default file."""
        # The web UI runs in another process and edits the config file
        self.config.load_config()
        pool_id = self.config.get(f'sensor_pools.{sensor_type.value}')
        default = self.config.get('audio.default_file', 'HMGreeting.wav')
        if isinstance(pool_id, str) and pool_id.startswith('file:'):
            # A single clip assigned straight to the port
            clip = pool_id[len('file:'):]
            if clip in self.audio_controller.list_audio_files():
                return clip
            self.logger.warning(f"Clip '{clip}' assigned to {sensor_type.value} is missing; playing the default")
            return default
        return self.greeting_picker.pick(pool_id, port=sensor_type.value) or default

    def trigger_network_performance(self, audio_file: Optional[str] = None,
                                    pool_id: Optional[str] = None,
                                    trigger_id: Optional[str] = None) -> dict:
        """Start a performance initiated by a network trigger.

        An explicit audio_file wins; otherwise a greeting is picked from pool_id
        if given; otherwise the default file is used.
        Returns a dict with keys: success (bool), message (str).
        """
        # Prevent overlap with existing performance or cooldown
        if self.performance_active:
            return { 'success': False, 'message': 'Performance already active' }
        if self.sensor_manager.is_in_cooldown():
            return { 'success': False, 'message': 'In cooldown period' }

        # Determine audio file
        selected_audio = (audio_file
                          or self.greeting_picker.pick(pool_id, port=f'trigger:{trigger_id}')
                          or self.config.get('audio.default_file', 'HMGreeting.wav'))

        self.performance_active = True
        source = self._source_for(trigger_id)
        try:
            # Get audio duration
            audio_duration = self.audio_controller.get_audio_duration(selected_audio)
            if not audio_duration:
                self.logger.error(f"Could not get duration for audio file: {selected_audio}")
                self._perf_record('error', selected_audio, source, reason='bad audio file')
                self.performance_active = False
                return { 'success': False, 'message': 'Invalid audio file' }

            # Turn on eyes immediately for duration
            self.led_controller.eyes_on_during_audio(audio_duration)

            # Start audio playback with completion callback
            self._perf_started(selected_audio, source)
            audio_started = self.audio_controller.play_audio_file(
                selected_audio,
                self._performance_complete
            )

            if not audio_started:
                self.logger.error("Failed to start audio playback")
                self._perf_record('error', selected_audio, source, reason='could not start')
                self._perf = None
                self.led_controller.turn_off_eyes()
                self.performance_active = False
                return { 'success': False, 'message': 'Failed to start audio playback' }

            # Start synchronized motor movements (sensor type labeled as 'network')
            self.motor_controller.start_synchronized_movement(
                audio_duration,
                selected_audio,
                'network'
            )

            self.current_audio = selected_audio
            self.logger.info(f"Network-triggered performance started - Duration: {audio_duration:.1f}s")
            return { 'success': True, 'message': 'Performance started' }

        except Exception as e:
            self.logger.error(f"Error starting network-triggered performance: {e}")
            self._perf_record('error', selected_audio, source, reason='exception')
            self._perf = None
            self.performance_active = False
            self._cleanup_performance()
            return { 'success': False, 'message': 'Unexpected error starting performance' }

    def live_command(self, command: str, body: dict) -> dict:
        """Operator actions from the web UI's Live tab.

        play  {audio_file | pool_id}  play now; an operator press ends any cooldown first
        sensor {sensor}               run a sensor port's path exactly as a visitor would
                                      (cooldown applies)
        stop                          cut the current performance
        """
        if command == 'stop':
            was_active = self.performance_active
            self.stop_performance()
            self.force_end_cooldown()
            return {'success': True, 'message': 'Stopped' if was_active else 'Nothing was playing'}
        if command == 'sensor_test':
            self.sensor_manager.set_test_mode(bool(body.get('on')))
            return {'success': True, 'test_mode': self.sensor_manager.in_test_mode()}
        if command == 'sensor':
            try:
                sensor_type = SensorType(body.get('sensor'))
            except ValueError:
                return {'success': False, 'message': 'Unknown sensor'}
            if self.performance_active:
                return {'success': False, 'message': 'Performance already active'}
            if self.sensor_manager.is_in_cooldown():
                return {'success': False, 'message': 'In cooldown period'}
            self._start_performance(sensor_type, source='live')
            return {'success': self.performance_active, 'message': 'Performance started' if self.performance_active else 'Failed to start'}
        if command == 'play':
            if self.performance_active:
                return {'success': False, 'message': 'Performance already active'}
            self.force_end_cooldown()
            return self.trigger_network_performance(body.get('audio_file'), body.get('pool_id'), 'live')
        return {'success': False, 'message': 'Unknown command'}

    def _start_performance(self, sensor_type: SensorType, source: str = 'sensor'):
        """Start the main animatronic performance"""
        self.performance_active = True
        audio_file = None
        
        try:
            # Get audio file to play
            audio_file = self._sensor_audio_file(sensor_type)
            
            # Get audio duration
            audio_duration = self.audio_controller.get_audio_duration(audio_file)
            if not audio_duration:
                self.logger.error(f"Could not get duration for audio file: {audio_file}")
                self._perf_record('error', audio_file, source, port=sensor_type.value, reason='bad audio file')
                self.performance_active = False   # was left set, which made the prop look busy forever
                return
            
            # Turn on eyes immediately
            self.led_controller.eyes_on_during_audio(audio_duration)
            
            # Start audio playback with completion callback
            self._perf_started(audio_file, source, port=sensor_type.value)
            audio_started = self.audio_controller.play_audio_file(
                audio_file, 
                self._performance_complete
            )
            
            if not audio_started:
                self.logger.error("Failed to start audio playback")
                self._perf_record('error', audio_file, source, port=sensor_type.value, reason='could not start')
                self._perf = None
                self.led_controller.turn_off_eyes()
                self.performance_active = False
                return
            
            # Start synchronized motor movements
            self.motor_controller.start_synchronized_movement(
                audio_duration, 
                audio_file, 
                sensor_type.value
            )
            
            self.current_audio = audio_file
            self.logger.info(f"Performance started - Duration: {audio_duration:.1f}s")
            
        except Exception as e:
            self.logger.error(f"Error starting performance: {e}")
            self._perf_record('error', audio_file, source, port=sensor_type.value, reason='exception')
            self._perf = None
            self.performance_active = False
            self._cleanup_performance()
    
    def _performance_complete(self):
        """Called when audio playback completes"""
        self.logger.info("Performance completed")
        self.performance_active = False
        if self._perf:
            result = getattr(self.audio_controller, 'last_result', None) or 'ok'
            self._perf_record(result)
            self._perf = None
        
        # Start cooldown period
        self.sensor_manager.start_cooldown()
        
        # Ensure everything is stopped
        self._cleanup_performance()
    
    def _cleanup_performance(self):
        """Clean up after performance"""
        self.current_audio = None
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