#!/usr/bin/env python3
"""
Audio Test Script for Ghost Host
===============================
Plays the default audio file using aplay (system audio player).
"""
import sys
from pathlib import Path
import subprocess
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from core.config_manager import config

settings = config.get_audio_settings()
audio_file = settings.get('default_file', 'HMGreeting.wav')
soundfiles_dir = settings.get('soundfiles_dir', 'SoundFiles')
audio_path = Path(soundfiles_dir) / audio_file

print(f"Attempting to play audio with aplay: {audio_path}")

if not audio_path.exists():
    print(f"ERROR: Audio file not found: {audio_path}")
    exit(1)

try:
    result = subprocess.run(['aplay', str(audio_path)], capture_output=True, text=True)
    if result.returncode == 0:
        print("Audio playback complete.")
    else:
        print(f"ERROR: aplay failed: {result.stderr}")
except Exception as e:
    print(f"ERROR: Failed to play audio: {e}") 