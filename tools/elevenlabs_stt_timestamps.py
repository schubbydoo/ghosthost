import os
import sys
import requests
import json
from dotenv import load_dotenv

SOUNDFILES_DIR = "SoundFiles"
API_URL = "https://api.elevenlabs.io/v1/speech-to-text"
MODEL_ID = "scribe_v1"


def list_audio_files():
    files = [f for f in os.listdir(SOUNDFILES_DIR) if f.lower().endswith((".wav", ".mp3", ".ogg", ".flac", ".m4a"))]
    return files


def select_audio_file(files):
    print("Available audio files:")
    for idx, fname in enumerate(files):
        print(f"  [{idx+1}] {fname}")
    while True:
        choice = input(f"Select a file [1-{len(files)}]: ")
        if choice.isdigit() and 1 <= int(choice) <= len(files):
            return files[int(choice)-1]
        print("Invalid selection. Try again.")


def main():
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("Error: ELEVENLABS_API_KEY not found in .env file.")
        sys.exit(1)

    files = list_audio_files()
    if not files:
        print(f"No audio files found in {SOUNDFILES_DIR}/.")
        sys.exit(1)
    audio_file = select_audio_file(files)
    audio_path = os.path.join(SOUNDFILES_DIR, audio_file)
    out_json = os.path.splitext(audio_file)[0] + "_timestamps.json"
    out_path = os.path.join(SOUNDFILES_DIR, out_json)

    print(f"Uploading {audio_file} to Elevenlabs STT API...")
    with open(audio_path, "rb") as f:
        files = {"file": (audio_file, f)}
        data = {
            "model_id": MODEL_ID,
            "timestamps_granularity": "word",
            "tag_audio_events": "true"
        }
        headers = {
            "xi-api-key": api_key
        }
        try:
            response = requests.post(API_URL, headers=headers, data=data, files=files)
        except Exception as e:
            print(f"Request failed: {e}")
            sys.exit(1)

    if response.status_code != 200:
        print(f"API Error: {response.status_code} {response.text}")
        sys.exit(1)

    try:
        result = response.json()
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        sys.exit(1)

    with open(out_path, "w") as out_f:
        json.dump(result, out_f, indent=2)
    print(f"Timestamps JSON saved to {out_path}")

if __name__ == "__main__":
    main() 