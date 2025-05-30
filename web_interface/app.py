import sys
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
import socket
import os
import subprocess
import logging

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config_manager import config
from src.hardware.audio_controller import AudioController
from src.network_management.network_manager import NetworkManager
from src.network_management.ap_mode_manager import AP_SSID as DEFAULT_AP_SETUP_SSID

audio_controller = AudioController(config)
network_manager = NetworkManager()

app = Flask(__name__)

# Configure basic logging for the app if not already present
if not app.debug:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@app.route('/')
def home():
    is_ap_mode, ap_ssid = network_manager.get_ap_mode_status()
    return render_template('index.html', is_ap_mode=is_ap_mode, ap_ssid=ap_ssid or DEFAULT_AP_SETUP_SSID)

# --- AUDIO MANAGEMENT API ---

@app.route('/api/audio/files', methods=['GET'])
def list_audio_files_api():
    files = audio_controller.list_audio_files()
    default_file = config.get('audio.default_file', '')
    file_infos = []
    for filename in files:
        info = audio_controller.get_audio_info(filename)
        file_infos.append({
            'filename': filename,
            'is_default': filename == default_file,
            'has_timestamps': info.get('has_timestamps', False) if info else False
        })
    return jsonify({'files': file_infos, 'default': default_file})

@app.route('/api/audio/info/<path:filename>', methods=['GET'])
def get_audio_info_api(filename):
    info = audio_controller.get_audio_info(filename)
    if info:
        return jsonify(info)
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/audio/upload', methods=['POST'])
def upload_audio_file_api():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    from werkzeug.utils import secure_filename
    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({'error': 'Invalid filename'}), 400

    file_data = file.read()
    
    success = audio_controller.upload_audio_file(file_data, filename)
    if success:
        return jsonify({'success': True, 'filename': filename})
    return jsonify({'error': 'Upload failed'}), 500

@app.route('/api/audio/delete/<path:filename>', methods=['DELETE'])
def delete_audio_file_api(filename):
    success = audio_controller.delete_audio_file(filename)
    if success:
        return jsonify({'success': True})
    return jsonify({'error': 'Delete failed'}), 500

@app.route('/api/audio/default', methods=['POST'])
def set_default_audio_api():
    data = request.get_json()
    filename = data.get('filename')
    if not filename:
        return jsonify({'error': 'No filename provided'}), 400
    if filename not in audio_controller.list_audio_files():
        return jsonify({'error': 'File not found or invalid'}), 404

    config.set('audio.default_file', filename)
    config.save_config()
    return jsonify({'success': True, 'default': filename})

@app.route('/api/audio/volume', methods=['GET', 'POST'])
def audio_volume_api():
    if request.method == 'GET':
        volume = audio_controller.get_volume()
        return jsonify({'volume': volume})
    else:
        data = request.get_json()
        volume = data.get('volume')
        if volume is None or not isinstance(volume, int) or not (0 <= volume <= 100):
            return jsonify({'error': 'Invalid volume provided (must be int 0-100)'}), 400
        success = audio_controller.set_volume(int(volume))
        if success:
            config.save_config()
            return jsonify({'success': True, 'volume': int(volume)})
        return jsonify({'error': 'Failed to set volume'}), 500

@app.route('/api/audio/generate_timestamps/<path:filename>', methods=['POST'])
def generate_timestamps_api(filename):
    app.logger.info(f"Received request to generate timestamps for: {filename}")
    safe_filename = os.path.basename(filename)
    if safe_filename != filename or safe_filename not in audio_controller.list_audio_files():
        app.logger.error(f"Timestamp generation rejected for invalid/non-existent file: {filename}")
        return jsonify({'error': 'Invalid or non-existent audio file provided'}), 400

    script_path = os.path.join(Path(__file__).parent.parent, "tools", "elevenlabs_stt_timestamps.py")
    soundfiles_dir = config.get('audio.soundfiles_dir', 'SoundFiles')
    audio_file_path_in_soundfiles = os.path.join(soundfiles_dir, safe_filename)

    env = os.environ.copy()

    try:
        app.logger.info(f"Executing timestamp script: {sys.executable} {script_path} '{safe_filename}'")
        process = subprocess.run(
            [sys.executable, script_path, safe_filename],
            capture_output=True, text=True, check=True, timeout=120,
            cwd=str(Path(__file__).parent.parent)
        )
        app.logger.info(f"Timestamp script stdout: {process.stdout}")
        expected_json_filename = os.path.splitext(safe_filename)[0] + "_timestamps.json"
        expected_json_path = os.path.join(Path(__file__).parent.parent, soundfiles_dir, expected_json_filename)

        if os.path.exists(expected_json_path):
            return jsonify({'success': True, 'message': f'Timestamps generated for {safe_filename}', 'output': process.stdout})
        else:
            app.logger.error(f"Timestamp script ran but JSON file not found: {expected_json_path}")
            app.logger.error(f"Script stderr: {process.stderr}")
            return jsonify({'success': False, 'error': 'Timestamp generation script ran but output file not found.', 'details': process.stderr}), 500

    except subprocess.CalledProcessError as e:
        app.logger.error(f"Timestamp script execution failed for {safe_filename}. Return code: {e.returncode}")
        app.logger.error(f"Stdout: {e.stdout}")
        app.logger.error(f"Stderr: {e.stderr}")
        return jsonify({'error': 'Timestamp generation script failed.', 'details': e.stderr or e.stdout}), 500
    except subprocess.TimeoutExpired:
        app.logger.error(f"Timestamp script timed out for {safe_filename}.")
        return jsonify({'error': 'Timestamp generation timed out.'}), 500
    except Exception as e:
        app.logger.error(f"An unexpected error occurred during timestamp generation for {safe_filename}: {str(e)}")
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

# Serve audio files for playback/download
@app.route('/SoundFiles/<path:filename>')
def serve_audio_file(filename):
    audio_dir = config.get('audio.soundfiles_dir', 'SoundFiles')
    project_root_soundfiles = os.path.join(app.root_path, '..', audio_dir)
    return send_from_directory(os.path.abspath(project_root_soundfiles), filename)

@app.route('/api/status', methods=['GET'])
def get_status():
    status = {}
    def get_lan_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception as e:
            app.logger.warning(f"Could not get LAN IP: {e}")
            return 'Unavailable'
            
    status['ip_address'] = get_lan_ip()
    status['current_network_ssid'] = network_manager.get_current_ssid() or "Not Connected"
    
    is_ap_active, ap_mode_ssid = network_manager.get_ap_mode_status()
    status['ap_mode_active'] = is_ap_active
    status['ap_mode_ssid'] = ap_mode_ssid if is_ap_active else None
    if is_ap_active:
        status['ap_mode_ip'] = DEFAULT_AP_IP_CIDR.split('/')[0]

    status['cooldown_period'] = config.get('app.cooldown_period', 30)
    status['default_audio_file'] = config.get('audio.default_file', 'N/A')

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

# --- SYSTEM COMMANDS ---
@app.route('/api/system/reboot', methods=['POST'])
def system_reboot():
    try:
        subprocess.run(['sudo', 'reboot'], check=True, timeout=5)
        return jsonify({'success': True, 'message': 'System is rebooting...'}), 200
    except subprocess.CalledProcessError as e:
        app.logger.error(f"Reboot command failed: {e}")
        return jsonify({'success': False, 'message': f'Reboot failed: {e.stderr or e.stdout or str(e)}'}), 500
    except subprocess.TimeoutExpired:
        app.logger.info("Reboot command initiated (timed out waiting for completion, which is expected).")
        return jsonify({'success': True, 'message': 'Reboot command initiated. The server will go down.'}), 202
    except Exception as e:
        app.logger.error(f"An unexpected error occurred during reboot: {e}")
        return jsonify({'success': False, 'message': f'An unexpected error occurred: {str(e)}'}), 500

@app.route('/api/config/cooldown', methods=['GET'])
def get_cooldown_api():
    cooldown = config.get('sensors.cooldown_period', 30)
    return jsonify({'cooldown_period': cooldown})

@app.route('/api/config/cooldown', methods=['POST'])
def set_cooldown_api():
    data = request.get_json()
    cooldown = data.get('cooldown_period')
    if cooldown is None or not isinstance(cooldown, int) or cooldown < 0 or cooldown > 600:
        return jsonify({'error': 'Invalid cooldown value (must be int 0-600 seconds)'}), 400
    config.set('sensors.cooldown_period', cooldown)
    config.save_config()
    return jsonify({'success': True, 'cooldown_period': cooldown})

@app.route('/api/idle_behavior', methods=['GET'])
def get_idle_behavior_api():
    settings = config.get_idle_behavior_settings()
    return jsonify(settings)

@app.route('/api/idle_behavior', methods=['POST'])
def set_idle_behavior_api():
    data = request.get_json()
    enabled = data.get('enabled')
    interval = data.get('interval_seconds')
    duration = data.get('duration_seconds')
    # Validate
    if not isinstance(enabled, bool):
        return jsonify({'error': 'Enabled must be boolean'}), 400
    if not isinstance(interval, int) or interval < 10 or interval > 3600:
        return jsonify({'error': 'Interval must be 10-3600 seconds'}), 400
    if not isinstance(duration, int) or duration < 1 or duration > 60:
        return jsonify({'error': 'Duration must be 1-60 seconds'}), 400
    config.set('idle_behavior.enabled', enabled)
    config.set('idle_behavior.interval_seconds', interval)
    config.set('idle_behavior.duration_seconds', duration)
    config.save_config()
    return jsonify({'success': True, 'idle_behavior': config.get_idle_behavior_settings()})

if __name__ == '__main__':
    app.run(host=config.get('web.host', '0.0.0.0'), 
            port=config.get('web.port', 8000), 
            debug=config.get('web.debug', True))
