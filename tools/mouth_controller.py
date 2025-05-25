"""
Animatronic Mouth Controller
----------------------------
- Uses DRV8833 motor driver connected to GPIO 22 and 23
- Opens and closes the mouth in sync with word timestamps
- Audio and its JSON timestamp file are in the SoundFiles directory
- JSON file must be named: <audio_filename>_timestamps.json
"""

import json
import RPi.GPIO as GPIO
import time
import threading
import os
import subprocess
from pathlib import Path

# === CONFIGURATION ===
AUDIO_FILENAME = "HMGreeting.wav"
# Use absolute path to SoundFiles directory
SOUNDFILES_DIR = Path(__file__).resolve().parent.parent / "SoundFiles"
JSON_FILENAME = AUDIO_FILENAME.replace(".wav", "_timestamps.json")
AUDIO_PATH = SOUNDFILES_DIR / AUDIO_FILENAME
JSON_PATH = SOUNDFILES_DIR / JSON_FILENAME

# GPIO setup for DRV8833
AIN1 = 23  # Motor input 1
AIN2 = 22  # Motor input 2

GPIO.setmode(GPIO.BCM)
GPIO.setup(AIN1, GPIO.OUT)
GPIO.setup(AIN2, GPIO.OUT)

def mouth_open():
    """Activate motor to open mouth"""
    GPIO.output(AIN1, GPIO.HIGH)
    GPIO.output(AIN2, GPIO.LOW)

def mouth_close():
    """Stop motor to close mouth (spring return)"""
    GPIO.output(AIN1, GPIO.LOW)
    GPIO.output(AIN2, GPIO.LOW)

def play_audio(audio_path):
    """Play the audio file using aplay subprocess"""
    subprocess.run(['aplay', str(audio_path)])

def animate_mouth(words_json):
    """Open and close mouth based on Elevenlabs word timestamp data"""
    # Extract only 'word' type entries
    word_entries = [w for w in words_json if w.get('type') == 'word']
    start_time = time.time()
    for word in word_entries:
        word_start = word['start']
        word_end = word['end']
        current_time = time.time() - start_time
        sleep_time = word_start - current_time
        if sleep_time > 0:
            time.sleep(sleep_time)
        mouth_open()
        time.sleep(word_end - word_start)
        mouth_close()

def main():
    # Load JSON word timestamps
    if not JSON_PATH.exists():
        print(f"ERROR: Timestamp file not found: {JSON_PATH}")
        return
    with open(JSON_PATH, "r") as f:
        json_data = json.load(f)
    # Elevenlabs format: top-level 'words' list
    words_json = json_data.get('words', [])
    # Run audio and mouth threads in parallel
    audio_thread = threading.Thread(target=play_audio, args=(AUDIO_PATH,))
    mouth_thread = threading.Thread(target=animate_mouth, args=(words_json,))
    audio_thread.start()
    mouth_thread.start()
    audio_thread.join()
    mouth_thread.join()
    GPIO.cleanup()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        GPIO.cleanup()
