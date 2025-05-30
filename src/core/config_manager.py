"""
Configuration Manager for Ghost Host
===================================
Handles loading, validating, and updating configuration settings.
"""

import yaml
import os
import logging
from typing import Dict, Any
from pathlib import Path

class ConfigManager:
    def __init__(self, config_path: str = "config/default_config.yaml"):
        self.config_path = Path(config_path)
        self.config = {}
        self.logger = logging.getLogger(__name__)
        self.load_config()
    
    def load_config(self):
        """Load configuration from YAML file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as file:
                    self.config = yaml.safe_load(file)
                self.logger.info(f"Configuration loaded from {self.config_path}")
            else:
                self.logger.error(f"Configuration file not found: {self.config_path}")
                self.config = self._get_default_config()
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            self.config = self._get_default_config()
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w') as file:
                yaml.dump(self.config, file, default_flow_style=False, indent=2)
            self.logger.info(f"Configuration saved to {self.config_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
            return False
    
    def get(self, key_path: str, default=None):
        """Get configuration value using dot notation (e.g., 'audio.volume')"""
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any):
        """Set configuration value using dot notation"""
        keys = key_path.split('.')
        config = self.config
        
        # Navigate to the parent of the final key
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # Set the final value
        config[keys[-1]] = value
    
    def update_from_dict(self, updates: Dict[str, Any]):
        """Update configuration from a dictionary"""
        for key_path, value in updates.items():
            self.set(key_path, value)
    
    def get_gpio_pins(self) -> Dict[str, int]:
        """Get all GPIO pin assignments"""
        return self.get('hardware.gpio', {})
    
    def get_audio_settings(self) -> Dict[str, Any]:
        """Get audio configuration"""
        return self.get('audio', {})
    
    def get_sensor_settings(self) -> Dict[str, Any]:
        """Get sensor configuration"""
        return self.get('sensors', {})
    
    def get_motor_settings(self) -> Dict[str, Any]:
        """Get motor configuration"""
        return self.get('motors', {})
    
    def get_network_settings(self) -> Dict[str, Any]:
        """Get network configuration"""
        return self.get('network', {})
    
    def get_web_settings(self) -> Dict[str, Any]:
        """Get web interface configuration"""
        return self.get('web', {})
    
    def get_idle_behavior_settings(self) -> Dict[str, Any]:
        """Get idle behavior configuration"""
        return self.get('idle_behavior', {})
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return minimal default configuration if file loading fails"""
        return {
            'hardware': {
                'gpio': {
                    'led_eyes': 15,
                    'sensor_port_left': 9,
                    'sensor_port_right': 25,
                    'motor_head_in1': 4,
                    'motor_head_in2': 14,
                    'motor_torso_in1': 17,
                    'motor_torso_in2': 18,
                    'motor_mouth_in1': 22,
                    'motor_mouth_in2': 23,
                }
            },
            'audio': {
                'default_file': 'HMGreeting.wav',
                'volume': 80,
                'soundfiles_dir': 'SoundFiles'
            },
            'sensors': {
                'debounce_time': 0.2,
                'cooldown_period': 30
            },
            'motors': {
                'head_torso_duration': 0,
                'mouth_open_duration': 0.1,
                'mouth_close_delay': 0.05
            },
            'network': {
                'ap_mode': {
                    'ssid': 'ghosthost',
                    'password': '',
                    'ip_address': '192.168.4.1',
                    'subnet': '192.168.4.0/24',
                    'timeout': 300
                },
                'fallback_ssid': ''
            },
            'web': {
                'host': '0.0.0.0',
                'port': 8000,
                'debug': False
            },
            'idle_behavior': {
                'enabled': False,
                'interval_seconds': 120,
                'duration_seconds': 5
            },
            'logging': {
                'level': 'INFO',
                'file': 'logs/ghosthost.log',
                'max_size': '10MB',
                'backup_count': 5
            }
        }

# Global configuration instance
config = ConfigManager() 