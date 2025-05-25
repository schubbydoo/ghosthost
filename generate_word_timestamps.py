import openai
import json
import os
from dotenv import load_dotenv

# Load API key from .env
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Path to audio file
audio_path = "SoundFiles/HMGreeting.wav"

# Transcribe using Whisper API with word timestamps
with open(audio_path, "rb") as audio_file:
    transcript = openai.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        response_format="verbose_json",
        timestamp_granularity="word"
    )

# Extract relevant data
word_timestamps = []
for segment in transcript.get("words", []):
    word_timestamps.append({
        "word": segment["word"],
        "start": segment["start"],
        "end": segment["end"]
    })

# Save to JSON
output_path = "HMGreeting_transcript.json"
with open(output_path, "w") as outfile:
    json.dump(word_timestamps, outfile, indent=2)

print(f"Saved timestamped transcript to {output_path}")
