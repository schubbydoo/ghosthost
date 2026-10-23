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
        self._proc = None  # running aplay, so stop_audio can really stop it
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
    
    # --- Per-file gain -------------------------------------------------------
    # The system volume tops out at 100%, and a small USB speaker can still be too
    # quiet. A boost is baked into a cached copy with ffmpeg (a limiter keeps the
    # peaks from clipping, which also makes speech sound louder on tiny speakers).
    # Duration is unchanged, so mouth-sync still lines up.

    MAX_GAIN_DB = 20

    def get_gain(self, filename: str) -> float:
        gains = self.config.get('audio_gains', {}) or {}
        try:
            return float(gains.get(filename, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    def _gain_cache_dir(self) -> Path:
        return Path(self.audio_settings.get('soundfiles_dir', 'SoundFiles')) / '.gain_cache'

    def clear_gain_cache(self, filename: str):
        stem = Path(filename).stem
        for old in self._gain_cache_dir().glob(f'{stem}__*dB.wav'):
            try:
                old.unlink()
            except OSError:
                pass

    def gain_path(self, filename: str, gain_db: float) -> Optional[Path]:
        """Path of the boosted copy, rendering it if missing or older than the
        original. Returns None if it can't be made (caller plays the original)."""
        source = Path(self.audio_settings.get('soundfiles_dir', 'SoundFiles')) / filename
        out = self._gain_cache_dir() / f'{source.stem}__{gain_db:+.1f}dB.wav'
        try:
            if out.exists() and out.stat().st_mtime >= source.stat().st_mtime:
                return out
            out.parent.mkdir(exist_ok=True)
            tmp = out.with_suffix('.tmp.wav')
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(source),
                            '-af', f'volume={gain_db}dB,alimiter=limit=0.97',
                            '-c:a', 'pcm_s16le', str(tmp)],
                           check=True, capture_output=True, timeout=120)
            tmp.replace(out)
            return out
        except Exception as e:
            self.logger.error(f"Could not render {gain_db:+}dB copy of {filename}: {e}")
            return None

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

        # A per-file boost plays from a pre-rendered louder copy; the original
        # name is still what mouth-sync timestamps are looked up by.
        self.config.load_config()
        gain_db = self.get_gain(filename)
        if gain_db:
            audio_path = self.gain_path(filename, gain_db) or audio_path
        
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
            self._proc = subprocess.Popen(['aplay', audio_path], stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE, text=True)
            _, stderr = self._proc.communicate()
            if self._proc.returncode == 0:
                self.logger.info(f"Audio playback completed: {audio_path}")
            elif self._proc.returncode < 0:
                self.logger.info(f"Audio playback stopped: {audio_path}")
            else:
                self.logger.error(f"aplay failed: {stderr}")
        except Exception as e:
            self.logger.error(f"Error playing audio {audio_path}: {e}")
        finally:
            self._proc = None
            self.is_playing = False
            if self.playback_complete_callback:
                try:
                    self.playback_complete_callback()
                except Exception as e:
                    self.logger.error(f"Error in playback completion callback: {e}")
            self.playback_complete_callback = None
    
    def stop_audio(self):
        """Stop current audio playback"""
        proc = self._proc
        if proc and proc.poll() is None:
            proc.terminate()
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
    
    def upload_audio_file(self, file_data: bytes, filename: str) -> Optional[str]:
        """Store an uploaded audio file as a real .wav (aplay and the duration
        check only understand WAV). Returns the saved filename, or None on failure."""
        try:
            soundfiles_dir = self.audio_settings.get('soundfiles_dir', 'SoundFiles')
            audio_dir = Path(soundfiles_dir)
            audio_dir.mkdir(exist_ok=True)

            audio_path = audio_dir / (Path(filename).stem + '.wav')

            if file_data[:4] == b'RIFF' and file_data[8:12] == b'WAVE':
                audio_path.write_bytes(file_data)
            else:
                # mp3, m4a, ogg, flac...: convert
                src = audio_dir / f'.upload-{os.getpid()}-{Path(filename).name}'
                tmp = audio_path.with_name('.converting-' + audio_path.name)
                try:
                    src.write_bytes(file_data)
                    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(src),
                                    '-c:a', 'pcm_s16le', '-f', 'wav', str(tmp)],
                                   check=True, capture_output=True, timeout=120)
                    tmp.replace(audio_path)
                finally:
                    src.unlink(missing_ok=True)
                    tmp.unlink(missing_ok=True)

            self.logger.info(f"Audio file uploaded: {audio_path.name}")
            return audio_path.name

        except Exception as e:
            detail = getattr(e, 'stderr', b'') or b''
            self.logger.error(f"Error uploading audio file {filename}: {e} {detail.decode(errors='replace')[:200]}")
            return None

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
            self.clear_gain_cache(filename)
            
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