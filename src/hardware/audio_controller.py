"""
Audio Controller for Ghost Host
==============================
Handles audio playback with volume control and integration with motor synchronization.
"""

import os
import time
import threading
import logging
import subprocess
from pathlib import Path
import wave
from typing import Optional, Callable

class AudioController:
    def __init__(self, config):
        self.config = config
        self.audio_settings = config.get_audio_settings()
        self.logger = logging.getLogger(__name__)
        
        # Audio state tracking
        self.is_playing = False
        self.current_audio_thread = None
        self.playback_complete_callback = None
        
        self.logger.info("Audio Controller initialized")
    
    def set_volume(self, volume: int):
        """Set system volume (0-100)"""
        try:
            # Clamp volume to valid range
            volume = max(0, min(100, volume))
            
            # Use amixer to set volume
            subprocess.run([
                'amixer', 'sset', 'Master', f'{volume}%'
            ], check=True, capture_output=True)
            
            # Update config
            self.config.set('audio.volume', volume)
            
            self.logger.info(f"Volume set to {volume}%")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error setting volume: {e}")
            return False
    
    def get_volume(self) -> int:
        """Get current system volume"""
        try:
            result = subprocess.run([
                'amixer', 'sget', 'Master'
            ], check=True, capture_output=True, text=True)
            
            # Parse volume from output
            lines = result.stdout.split('\n')
            for line in lines:
                if '[' in line and '%' in line:
                    # Extract percentage
                    start = line.find('[') + 1
                    end = line.find('%')
                    if start > 0 and end > start:
                        return int(line[start:end])
            
            return self.audio_settings.get('volume', 80)
            
        except (subprocess.CalledProcessError, ValueError) as e:
            self.logger.error(f"Error getting volume: {e}")
            return self.audio_settings.get('volume', 80)
    
    def play_audio_file(self, filename: str, completion_callback: Optional[Callable] = None) -> bool:
        """Play audio file with optional completion callback using aplay subprocess"""
        if self.is_playing:
            self.logger.warning("Audio already playing, ignoring new request")
            return False
        
        # Build full path to audio file
        soundfiles_dir = self.audio_settings.get('soundfiles_dir', 'SoundFiles')
        audio_path = Path(soundfiles_dir) / filename
        
        if not audio_path.exists():
            self.logger.error(f"Audio file not found: {audio_path}")
            return False
        
        self.is_playing = True
        self.playback_complete_callback = completion_callback
        
        # Start playback in a separate thread
        self.current_audio_thread = threading.Thread(
            target=self._play_audio_worker,
            args=(str(audio_path),),
            daemon=True
        )
        self.current_audio_thread.start()
        
        self.logger.info(f"Started playing audio: {filename}")
        return True
    
    def _play_audio_worker(self, audio_path: str):
        """Worker thread for audio playback using aplay subprocess"""
        try:
            result = subprocess.run(['aplay', audio_path], capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info(f"Audio playback completed: {audio_path}")
            else:
                self.logger.error(f"aplay failed: {result.stderr}")
        except Exception as e:
            self.logger.error(f"Error playing audio {audio_path}: {e}")
        finally:
            self.is_playing = False
            if self.playback_complete_callback:
                try:
                    self.playback_complete_callback()
                except Exception as e:
                    self.logger.error(f"Error in playback completion callback: {e}")
            self.playback_complete_callback = None
    
    def stop_audio(self):
        """Stop current audio playback"""
        if self.is_playing:
            self.is_playing = False
            # Note: pydub doesn't provide easy way to stop playback
            # In a production system, you might want to use a different audio library
            self.logger.info("Audio stop requested")
    
    def get_audio_duration(self, filename: str) -> Optional[float]:
        """Get duration of audio file in seconds using wave module"""
        try:
            soundfiles_dir = self.audio_settings.get('soundfiles_dir', 'SoundFiles')
            audio_path = Path(soundfiles_dir) / filename
            
            if not audio_path.exists():
                self.logger.error(f"Audio file not found: {audio_path}")
                return None
            
            with wave.open(str(audio_path), 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration = frames / float(rate)
            return duration
        except Exception as e:
            self.logger.error(f"Error getting audio duration for {filename}: {e}")
            return None
    
    def list_audio_files(self) -> list:
        """List all available audio files"""
        try:
            soundfiles_dir = self.audio_settings.get('soundfiles_dir', 'SoundFiles')
            audio_dir = Path(soundfiles_dir)
            
            if not audio_dir.exists():
                self.logger.warning(f"Audio directory not found: {audio_dir}")
                return []
            
            # Find all .wav files
            audio_files = []
            for file_path in audio_dir.glob('*.wav'):
                audio_files.append(file_path.name)
            
            return sorted(audio_files)
            
        except Exception as e:
            self.logger.error(f"Error listing audio files: {e}")
            return []
    
    def upload_audio_file(self, file_data: bytes, filename: str) -> bool:
        """Upload new audio file"""
        try:
            soundfiles_dir = self.audio_settings.get('soundfiles_dir', 'SoundFiles')
            audio_dir = Path(soundfiles_dir)
            audio_dir.mkdir(exist_ok=True)
            
            # Ensure filename has .wav extension
            if not filename.lower().endswith('.wav'):
                filename += '.wav'
            
            audio_path = audio_dir / filename
            
            # Write file
            with open(audio_path, 'wb') as f:
                f.write(file_data)
            
            self.logger.info(f"Audio file uploaded: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error uploading audio file {filename}: {e}")
            return False
    
    def delete_audio_file(self, filename: str) -> bool:
        """Delete audio file"""
        try:
            soundfiles_dir = self.audio_settings.get('soundfiles_dir', 'SoundFiles')
            audio_path = Path(soundfiles_dir) / filename
            
            if not audio_path.exists():
                self.logger.error(f"Audio file not found: {audio_path}")
                return False
            
            # Also delete corresponding timestamp file if it exists
            timestamp_file = filename.replace('.wav', '_timestamps.json')
            timestamp_path = Path(soundfiles_dir) / timestamp_file
            
            # Delete audio file
            audio_path.unlink()
            
            # Delete timestamp file if it exists
            if timestamp_path.exists():
                timestamp_path.unlink()
                self.logger.info(f"Deleted timestamp file: {timestamp_file}")
            
            self.logger.info(f"Audio file deleted: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting audio file {filename}: {e}")
            return False
    
    def get_audio_info(self, filename: str) -> Optional[dict]:
        """Get information about audio file"""
        try:
            soundfiles_dir = self.audio_settings.get('soundfiles_dir', 'SoundFiles')
            audio_path = Path(soundfiles_dir) / filename
            
            if not audio_path.exists():
                return None
            
            # Get file stats
            stat = audio_path.stat()
            
            # Get audio duration
            duration = self.get_audio_duration(filename)
            
            # Check for timestamp file
            timestamp_file = filename.replace('.wav', '_timestamps.json')
            timestamp_path = Path(soundfiles_dir) / timestamp_file
            has_timestamps = timestamp_path.exists()
            
            return {
                'filename': filename,
                'size': stat.st_size,
                'duration': duration,
                'has_timestamps': has_timestamps,
                'modified': stat.st_mtime
            }
            
        except Exception as e:
            self.logger.error(f"Error getting audio info for {filename}: {e}")
            return None
    
    def get_status(self) -> dict:
        """Get current audio controller status"""
        return {
            'is_playing': self.is_playing,
            'volume': self.get_volume(),
            'available_files': self.list_audio_files(),
            'default_file': self.audio_settings.get('default_file', ''),
            'soundfiles_dir': self.audio_settings.get('soundfiles_dir', 'SoundFiles')
        } 