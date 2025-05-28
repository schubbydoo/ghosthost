import sys
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
import socket
import fcntl
import struct
import os
import subprocess
import logging

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config_manager import config
from src.hardware.audio_controller import AudioController
from src.core.event_handler import EventHandler
from src.network_management.network_manager import NetworkManager

audio_controller = AudioController(config)
network_manager = NetworkManager()

app = Flask(__name__)

# Configure basic logging for the app if not already present
if not app.debug:
    logging.basicConfig(level=logging.INFO)

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
    def get_lan_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return 'Unavailable'
    status['ip_address'] = get_lan_ip()
    status['current_network'] = network_manager.get_current_ssid() or "Not Connected"
    status['ap_mode_active'], status['ap_ssid'] = network_manager.get_ap_mode_status()
    return jsonify(status)

# --- WIFI/NETWORK MANAGEMENT API (using NetworkManager) ---

@app.route('/api/networks', methods=['GET'])
def list_networks_api():
    available = network_manager.scan_wifi_networks()
    saved = network_manager.get_saved_networks()
    return jsonify({'available_networks': available, 'saved_networks': saved})

@app.route('/api/networks/connect', methods=['POST'])
def connect_network_api():
    data = request.get_json()
    ssid_or_uuid = data.get('ssid_or_uuid')
    password = data.get('password')
    if not ssid_or_uuid:
        return jsonify({'success': False, 'message': 'SSID or UUID required'}), 400
    
    success, msg = network_manager.connect_network(ssid_or_uuid, password)
    return jsonify({'success': success, 'message': msg})

@app.route('/api/networks/save', methods=['POST'])
def save_network_api():
    data = request.get_json()
    ssid = data.get('ssid')
    password = data.get('password')
    autoconnect = data.get('autoconnect', True)
    if not ssid or not password:
        return jsonify({'success': False, 'message': 'SSID and password required'}), 400
    
    success, msg = network_manager.save_network(ssid, password, autoconnect)
    return jsonify({'success': success, 'message': msg})

@app.route('/api/networks/delete', methods=['POST'])
def delete_network_api():
    data = request.get_json()
    name_or_uuid = data.get('name_or_uuid')
    if not name_or_uuid:
        return jsonify({'success': False, 'message': 'Name or UUID required'}), 400
    
    success, msg = network_manager.delete_network(name_or_uuid)
    return jsonify({'success': success, 'message': msg})

@app.route('/api/networks/disconnect', methods=['POST'])
def disconnect_network_api():
    data = request.get_json()
    name_or_uuid = data.get('name_or_uuid', None)
    success, msg = network_manager.disconnect_network(name_or_uuid)
    return jsonify({'success': success, 'message': msg})

@app.route('/api/networks/activate_ap', methods=['POST'])
def activate_ap_api():
    success, msg = network_manager.activate_ap_mode()
    return jsonify({'success': success, 'message': msg})

@app.route('/api/networks/deactivate_ap', methods=['POST'])
def deactivate_ap_api():
    success, msg = network_manager.deactivate_ap_mode()
    return jsonify({'success': success, 'message': msg})

if __name__ == '__main__':
    app.run(host=config.get('web.host', '0.0.0.0'), 
            port=config.get('web.port', 8000), 
            debug=config.get('web.debug', True))
