import os
import sys
import requests
import json
from dotenv import load_dotenv
import argparse

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
    parser = argparse.ArgumentParser(description="Generate word timestamps for an audio file using ElevenLabs STT API.")
    parser.add_argument("audio_filename", type=str, nargs="?", help="Name of the audio file in the SoundFiles directory.")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("Error: ELEVENLABS_API_KEY not found in .env file or environment.")
        sys.exit(1)

    if args.audio_filename:
        audio_file = args.audio_filename
        if not os.path.exists(os.path.join(SOUNDFILES_DIR, audio_file)):
            print(f"Error: Audio file '{audio_file}' not found in {SOUNDFILES_DIR}/.")
            files = list_audio_files()
            if files:
                print("\nAvailable audio files:")
                for fname in files:
                    print(f"  {fname}")
            else:
                print(f"No audio files found in {SOUNDFILES_DIR}/.")
            sys.exit(1)
    else:
        files = list_audio_files()
        if not files:
            print(f"No audio files found in {SOUNDFILES_DIR}/.")
            sys.exit(1)
        audio_file = select_audio_file(files)
    
    audio_path = os.path.join(SOUNDFILES_DIR, audio_file)
    base_audio_filename = os.path.basename(audio_file)
    out_json = os.path.splitext(base_audio_filename)[0] + "_timestamps.json"
    out_path = os.path.join(SOUNDFILES_DIR, out_json)

    print(f"Uploading {audio_file} to Elevenlabs STT API...")
    try:
        with open(audio_path, "rb") as f:
            files_payload = {"file": (base_audio_filename, f)}
            data = {
                "model_id": MODEL_ID,
                "timestamps_granularity": "word",
                "tag_audio_events": "true"
            }
            headers = {
                "xi-api-key": api_key
            }
            response = requests.post(API_URL, headers=headers, data=data, files=files_payload)
            response.raise_for_status()
            result = response.json()

    except requests.exceptions.RequestException as e:
        print(f"API Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}")
        print(f"Response content: {response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

    with open(out_path, "w") as out_f:
        json.dump(result, out_f, indent=2)
    print(f"Timestamps JSON saved to {out_path}")

if __name__ == "__main__":
    main() 