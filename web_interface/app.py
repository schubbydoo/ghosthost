import sys
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
import socket
import fcntl
import struct
import os

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config_manager import config
from src.hardware.audio_controller import AudioController
from src.core.event_handler import EventHandler

audio_controller = AudioController(config)

# Instantiate event handler for status
status_handler = EventHandler(config)

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

# --- AUDIO MANAGEMENT API ---

@app.route('/api/audio/files', methods=['GET'])
def list_audio_files():
    files = audio_controller.list_audio_files()
    default_file = config.get('audio.default_file', '')
    file_infos = []
    for filename in files:
        info = audio_controller.get_audio_info(filename)
        file_infos.append({
            'filename': filename,
            'is_default': filename == default_file,
            'has_timestamps': info['has_timestamps'] if info else False
        })
    return jsonify({'files': file_infos, 'default': default_file})

@app.route('/api/audio/info/<filename>', methods=['GET'])
def get_audio_info(filename):
    info = audio_controller.get_audio_info(filename)
    if info:
        return jsonify(info)
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/audio/upload', methods=['POST'])
def upload_audio_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    file_data = file.read()
    filename = file.filename
    success = audio_controller.upload_audio_file(file_data, filename)
    if success:
        return jsonify({'success': True})
    return jsonify({'error': 'Upload failed'}), 500

@app.route('/api/audio/delete/<filename>', methods=['DELETE'])
def delete_audio_file(filename):
    success = audio_controller.delete_audio_file(filename)
    if success:
        return jsonify({'success': True})
    return jsonify({'error': 'Delete failed'}), 500

@app.route('/api/audio/default', methods=['POST'])
def set_default_audio():
    data = request.get_json()
    filename = data.get('filename')
    if not filename:
        return jsonify({'error': 'No filename provided'}), 400
    config.set('audio.default_file', filename)
    config.save_config()
    return jsonify({'success': True, 'default': filename})

@app.route('/api/audio/volume', methods=['GET', 'POST'])
def audio_volume():
    if request.method == 'GET':
        volume = audio_controller.get_volume()
        return jsonify({'volume': volume})
    else:
        data = request.get_json()
        volume = data.get('volume')
        if volume is None:
            return jsonify({'error': 'No volume provided'}), 400
        success = audio_controller.set_volume(int(volume))
        if success:
            config.save_config()
            return jsonify({'success': True, 'volume': int(volume)})
        return jsonify({'error': 'Failed to set volume'}), 500

# Serve audio files for playback/download
@app.route('/SoundFiles/<path:filename>')
def serve_audio_file(filename):
    audio_dir = config.get('audio.soundfiles_dir', 'SoundFiles')
    return send_from_directory(audio_dir, filename)

@app.route('/api/status', methods=['GET'])
def get_status():
    status = {}
    # Get IP address (try to get LAN IP, not 127.0.1.1)
    def get_lan_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # This IP doesn't need to be reachable
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return 'Unavailable'
    status['ip_address'] = get_lan_ip()
    # TODO: Add current network info (SSID, etc.)
    return jsonify(status)

# --- WIFI/NETWORK MANAGEMENT API (stubs) ---
@app.route('/api/networks', methods=['GET'])
def list_networks():
    # TODO: Implement using nmcli or similar
    return jsonify({'networks': [], 'my_networks': []})

@app.route('/api/networks/connect', methods=['POST'])
def connect_network():
    # TODO: Implement connect logic
    return jsonify({'success': False, 'error': 'Not implemented'}), 501

@app.route('/api/networks/disconnect', methods=['POST'])
def disconnect_network():
    # TODO: Implement disconnect logic
    return jsonify({'success': False, 'error': 'Not implemented'}), 501

@app.route('/api/networks/add', methods=['POST'])
def add_network():
    # TODO: Implement add logic
    return jsonify({'success': False, 'error': 'Not implemented'}), 501

@app.route('/api/networks/delete', methods=['POST'])
def delete_network():
    # TODO: Implement delete logic
    return jsonify({'success': False, 'error': 'Not implemented'}), 501

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
