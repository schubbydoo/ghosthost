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
import requests
import uuid
import copy
from datetime import datetime
from src.core import schedule as sched
from src.core import timed_triggers as timed
from src.core import shows as shows_lib

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
    config.load_config()
    files = audio_controller.list_audio_files()
    default_file = config.get('audio.default_file', '')
    descriptions = config.get('audio_descriptions', {}) or {}
    live_files = set(config.get('live_files', []) or [])
    gains = config.get('audio_gains', {}) or {}
    # Which pools hold each file, in pool order, plus its position in each
    pools_by_file = {}
    for pool in config.get('greeting_pools', []) or []:
        for i, f in enumerate(pool.get('files') or []):
            pools_by_file.setdefault(f, []).append(
                {'id': pool.get('id'), 'name': pool.get('name'), 'position': i + 1})
    file_infos = []
    for filename in files:
        info = audio_controller.get_audio_info(filename) or {}
        file_infos.append({
            'filename': filename,
            'is_default': filename == default_file,
            'has_timestamps': info.get('has_timestamps', False),
            'description': descriptions.get(filename, ''),
            'live': filename in live_files,
            'gain_db': gains.get(filename, 0),
            'duration': info.get('duration'),
            'modified': info.get('modified'),
            'pools': pools_by_file.get(filename, []),
        })
    return jsonify({'files': file_infos, 'default': default_file})

@app.route('/api/audio/gain', methods=['POST'])
def set_audio_gain_api():
    """Set a per-file volume boost in dB (0 clears it): {filename, gain_db}. The
    boosted copy is rendered now so the next play starts instantly."""
    config.load_config()
    data = request.get_json() or {}
    filename = data.get('filename')
    if filename not in audio_controller.list_audio_files():
        return jsonify({'error': 'File not found'}), 404
    try:
        gain = round(float(data.get('gain_db', 0)), 1)
    except (TypeError, ValueError):
        return jsonify({'error': 'gain_db must be a number'}), 400
    limit = audio_controller.MAX_GAIN_DB
    if not -limit <= gain <= limit:
        return jsonify({'error': f'gain_db must be between -{limit} and {limit}'}), 400
    gains = config.get('audio_gains', {}) or {}
    audio_controller.clear_gain_cache(filename)
    if gain:
        if not audio_controller.gain_path(filename, gain):
            return jsonify({'error': 'Could not render the boosted copy (is ffmpeg installed?)'}), 500
        gains[filename] = gain
    else:
        gains.pop(filename, None)
    config.set('audio_gains', gains)
    config.save_config()
    return jsonify({'success': True, 'gain_db': gain})

@app.route('/api/audio/preview/<path:filename>')
def preview_audio_api(filename):
    """The file as the prop will play it (with its boost), for the browser player."""
    safe = os.path.basename(filename)
    if safe not in audio_controller.list_audio_files():
        return jsonify({'error': 'File not found'}), 404
    config.load_config()
    path = None
    gain = audio_controller.get_gain(safe)
    if gain:
        path = audio_controller.gain_path(safe, gain)
    if not path:
        soundfiles = os.path.abspath(os.path.join(app.root_path, '..', config.get('audio.soundfiles_dir', 'SoundFiles')))
        return send_from_directory(soundfiles, safe)
    return send_from_directory(os.path.dirname(os.path.abspath(path)), os.path.basename(path))

@app.route('/api/audio/description', methods=['POST'])
def set_audio_description_api():
    config.load_config()
    data = request.get_json() or {}
    filename = data.get('filename')
    if filename not in audio_controller.list_audio_files():
        return jsonify({'error': 'File not found'}), 404
    descriptions = config.get('audio_descriptions', {}) or {}
    text = (data.get('description') or '').strip()
    if text:
        descriptions[filename] = text
    else:
        descriptions.pop(filename, None)
    config.set('audio_descriptions', descriptions)
    config.save_config()
    return jsonify({'success': True})

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

# --- LIVE TAB API ---

def _controller_post(path, body):
    port = config.get('network_trigger.port', 5055)
    try:
        r = requests.post(f'http://127.0.0.1:{port}/api/live/{path}', json=body, timeout=5)
        return r.json()
    except Exception:
        return {'success': False, 'message': 'Controller not responding'}

@app.route('/api/live/state', methods=['GET'])
def live_state():
    config.load_config()
    descriptions = config.get('audio_descriptions', {}) or {}
    available = audio_controller.list_audio_files()
    live_files = [f for f in (config.get('live_files', []) or []) if f in available]
    assignments = config.get('sensor_pools', {}) or {}
    def ref_label(ref):
        if isinstance(ref, str) and ref.startswith('file:'):
            return descriptions.get(ref[5:]) or ref[5:]
        if sched.is_schedule_ref(ref):
            sc = sched.get_schedule(config, sched.schedule_id_from_ref(ref))
            return 'Schedule: ' + sc['name'] if sc else None
        pool = _find_pool(ref) if ref else None
        return pool['name'] if pool else None
    active_show = shows_lib.get_show(config, config.get('active_show'))
    return jsonify({
        'show': active_show.get('name') if active_show else '',
        'messages': [{'filename': f, 'description': descriptions.get(f, '')} for f in live_files],
        'pools': [{'id': p['id'], 'name': p['name'], 'count': len(p.get('files') or [])}
                  for p in config.get('greeting_pools', []) or []],
        'schedules': [{'id': 'schedule:' + sc['id'], 'name': sc['name']}
                      for sc in config.get('schedules', []) or []],
        'sensors': [{'id': p, 'label': 'Left sensor' if p.endswith('left') else 'Right sensor',
                     'assigned': ref_label(assignments.get(p)) or 'default audio'} for p in SENSOR_PORTS],
    })

@app.route('/api/live/play', methods=['POST'])
def live_play():
    config.load_config()
    data = request.get_json() or {}
    if data.get('audio_file'):
        if data['audio_file'] not in audio_controller.list_audio_files():
            return jsonify({'success': False, 'message': 'File not found'}), 404
        body = {'audio_file': data['audio_file']}
    elif data.get('pool_id') and _valid_ref(data['pool_id']):
        body = {'pool_id': data['pool_id']}
    else:
        return jsonify({'success': False, 'message': 'Nothing to play'}), 400
    return jsonify(_controller_post('play', body))

@app.route('/api/live/sensor', methods=['POST'])
def live_sensor():
    sensor = (request.get_json() or {}).get('sensor')
    if sensor not in SENSOR_PORTS:
        return jsonify({'success': False, 'message': 'Unknown sensor'}), 400
    return jsonify(_controller_post('sensor', {'sensor': sensor}))

@app.route('/api/live/sensors', methods=['GET'])
def live_sensor_levels():
    """Raw pin levels and recent level changes, for the sensor test on the Live tab"""
    port = config.get('network_trigger.port', 5055)
    try:
        since = int(request.args.get('since', 0))
        r = requests.get(f'http://127.0.0.1:{port}/api/live/sensors', params={'since': since}, timeout=2)
        return jsonify(r.json())
    except Exception:
        return jsonify({'success': False, 'message': 'Controller not responding'})

@app.route('/api/live/sensor_test', methods=['POST'])
def live_sensor_test():
    on = bool((request.get_json() or {}).get('on'))
    return jsonify(_controller_post('sensor_test', {'on': on}))

@app.route('/api/live/stop', methods=['POST'])
def live_stop():
    return jsonify(_controller_post('stop', {}))

@app.route('/api/live/favorite', methods=['POST'])
def live_favorite():
    """Show or hide a file as a button on the Live tab: {filename, on}"""
    config.load_config()
    data = request.get_json() or {}
    filename = data.get('filename')
    if filename not in audio_controller.list_audio_files():
        return jsonify({'error': 'File not found'}), 404
    files = [f for f in (config.get('live_files', []) or []) if f != filename]
    if data.get('on'):
        files.append(filename)
    config.set('live_files', files)
    config.save_config()
    return jsonify({'success': True})

@app.route('/api/health', methods=['GET'])
def get_health():
    """Dashboard health: is the controller process alive, what is it doing, and Pi vitals."""
    h = {'controller_up': False, 'performing': False, 'cooling_down': False, 'cooldown_remaining': 0}
    try:
        port = config.get('network_trigger.port', 5055)
        r = requests.get(f'http://127.0.0.1:{port}/api/status', timeout=1.5).json()
        h.update(controller_up=True, performing=bool(r.get('performing')),
                 now_playing=r.get('now_playing'),
                 cooling_down=bool(r.get('cooling_down')),
                 cooldown_remaining=r.get('cooldown_remaining', 0))
    except Exception:
        pass
    def read(path):
        try:
            with open(path) as f:
                return f.read()
        except OSError:
            return None
    up = read('/proc/uptime')
    h['uptime_seconds'] = int(float(up.split()[0])) if up else None
    t = read('/sys/class/thermal/thermal_zone0/temp')
    h['cpu_temp_c'] = int(t) / 1000 if t else None
    mem = {}
    for line in (read('/proc/meminfo') or '').splitlines():
        k, _, v = line.partition(':')
        mem[k] = int(v.split()[0]) if v.split() else 0
    h['mem_used_pct'] = (round(100 - 100 * mem['MemAvailable'] / mem['MemTotal'])
                         if mem.get('MemTotal') else None)
    try:
        import shutil
        du = shutil.disk_usage('/')
        h['disk_used_pct'] = round(100 * du.used / du.total)
    except OSError:
        h['disk_used_pct'] = None
    files = audio_controller.list_audio_files()
    h['audio_files'] = len(files)
    h['missing_timestamps'] = sum(1 for f in files
                                  if not (audio_controller.get_audio_info(f) or {}).get('has_timestamps'))
    h['default_audio'] = config.get('audio.default_file', '')
    return jsonify(h)

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

# --- GREETING POOLS API ---

SENSOR_PORTS = ['sensor_port_left', 'sensor_port_right']
TRIGGER_ACTIONS = ('play', 'advance', 'auto')

def _find_pool(pool_id):
    return next((p for p in config.get('greeting_pools', []) or []
                 if str(p.get('id')) == str(pool_id)), None)

def _valid_ref(ref):
    """A pool id or a 'schedule:<id>' reference to an existing schedule."""
    if sched.is_schedule_ref(ref):
        return sched.get_schedule(config, sched.schedule_id_from_ref(ref)) is not None
    return _find_pool(ref) is not None

def _pool_order(value):
    return 'in_order' if value == 'in_order' else 'shuffle'

def _clean_pool_files(files):
    """Keep only existing audio files, without duplicates, preserving order."""
    available = set(audio_controller.list_audio_files())
    if not isinstance(files, list):
        return None
    return [f for f in dict.fromkeys(files) if f in available]

@app.route('/api/greeting_pools', methods=['GET'])
def list_greeting_pools():
    config.load_config()
    assignments = config.get('sensor_pools', {}) or {}
    return jsonify({
        'pools': config.get('greeting_pools', []) or [],
        'schedules': config.get('schedules', []) or [],
        'sensor_pools': {port: assignments.get(port) or '' for port in SENSOR_PORTS},
    })

@app.route('/api/greeting_pools', methods=['POST'])
def create_greeting_pool():
    config.load_config()
    data = request.get_json() or {}
    name = (data.get('name') or '').strip() or 'New Pool'
    files = _clean_pool_files(data.get('files', []))
    if files is None:
        return jsonify({'error': 'files must be a list'}), 400
    pool = {'id': str(uuid.uuid4()), 'name': name, 'files': files,
            'order': _pool_order(data.get('order'))}
    pools = config.get('greeting_pools', []) or []
    pools.append(pool)
    config.set('greeting_pools', pools)
    config.save_config()
    return jsonify({'success': True, 'pool': pool})

@app.route('/api/greeting_pools/<pool_id>', methods=['PUT'])
def update_greeting_pool(pool_id):
    config.load_config()
    data = request.get_json() or {}
    pool = _find_pool(pool_id)
    if not pool:
        return jsonify({'error': 'Pool not found'}), 404
    if 'name' in data:
        pool['name'] = (data.get('name') or '').strip() or pool.get('name')
    if 'files' in data:
        files = _clean_pool_files(data.get('files'))
        if files is None:
            return jsonify({'error': 'files must be a list'}), 400
        pool['files'] = files
    if 'order' in data:
        pool['order'] = _pool_order(data.get('order'))
    config.save_config()
    return jsonify({'success': True, 'pool': pool})

def _disable_timed_triggers_using(ref):
    """A deleted pool or schedule must not leave a timed trigger that would fall back to
    the default audio at its set time: switch those triggers off instead."""
    for t in config.get('timed_triggers', []) or []:
        if str(t.get('pool_id')) == str(ref):
            t['pool_id'] = ''
            t['enabled'] = False

@app.route('/api/greeting_pools/<pool_id>', methods=['DELETE'])
def delete_greeting_pool(pool_id):
    config.load_config()
    for sc in config.get('schedules', []) or []:
        if any(str(st.get('pool_id')) == str(pool_id) for st in sc.get('steps') or []):
            return jsonify({'error': f"Pool is used by schedule '{sc.get('name')}'"}), 409
    pools = config.get('greeting_pools', []) or []
    new_pools = [p for p in pools if str(p.get('id')) != str(pool_id)]
    if len(new_pools) == len(pools):
        return jsonify({'error': 'Pool not found'}), 404
    config.set('greeting_pools', new_pools)
    # Unassign from sensors and network triggers; they fall back to their file/default
    assignments = config.get('sensor_pools', {}) or {}
    for port in list(assignments):
        if str(assignments[port]) == str(pool_id):
            assignments[port] = ''
    config.set('sensor_pools', assignments)
    for t in config.get('network_triggers', []) or []:
        if str(t.get('pool_id')) == str(pool_id):
            t['pool_id'] = ''
    _disable_timed_triggers_using(pool_id)
    config.save_config()
    return jsonify({'success': True})

def _valid_sensor_ref(ref):
    """What a sensor port can be given: a pool, a schedule, or one clip as 'file:<name>'."""
    if isinstance(ref, str) and ref.startswith('file:'):
        return ref[len('file:'):] in audio_controller.list_audio_files()
    return _valid_ref(ref)

@app.route('/api/sensor_pools', methods=['POST'])
def set_sensor_pool():
    """Assign a pool (or '' for none) to a sensor port: {sensor, pool_id}"""
    config.load_config()
    data = request.get_json() or {}
    sensor = data.get('sensor')
    pool_id = data.get('pool_id') or ''
    if sensor not in SENSOR_PORTS:
        return jsonify({'error': 'Invalid sensor'}), 400
    if pool_id and not _valid_sensor_ref(pool_id):
        return jsonify({'error': 'Invalid pool_id'}), 400
    config.set(f'sensor_pools.{sensor}', pool_id)
    config.save_config()
    return jsonify({'success': True, 'sensor': sensor, 'pool_id': pool_id})

# --- SCHEDULES API ---

def _clean_schedule(data):
    """Validate a schedule body. Returns (schedule fields, error)."""
    steps = []
    for st in data.get('steps') or []:
        at = str(st.get('at') or '')
        if sched.parse_hhmm(at) is None:
            return None, f"Invalid time '{at}' (use HH:MM)"
        if not _find_pool(st.get('pool_id')):
            return None, 'Every step needs an existing pool'
        steps.append({'at': at, 'pool_id': st['pool_id']})
    if not steps:
        return None, 'Add at least one step'
    rollover = data.get('night_rollover') or sched.DEFAULT_ROLLOVER
    if sched.parse_hhmm(rollover) is None:
        return None, 'Invalid night rollover'
    fields = {'name': (data.get('name') or '').strip() or 'New Schedule',
              'active_date': (data.get('active_date') or '').strip(),
              'night_rollover': rollover, 'steps': steps}
    if fields['active_date']:
        try:
            datetime.strptime(fields['active_date'], '%Y-%m-%d')
        except ValueError:
            return None, 'Active date must be YYYY-MM-DD'
    fields['steps'] = sched.sorted_steps(fields)
    times = [s['at'] for s in fields['steps']]
    dupes = sorted({t for t in times if times.count(t) > 1})
    if dupes:
        return None, f"Two steps start at {dupes[0]}"
    return fields, None

def _schedule_warnings(schedule):
    files_with_ts = {f for f in audio_controller.list_audio_files()
                     if (audio_controller.get_audio_info(f) or {}).get('has_timestamps')}
    missing = set()
    for st in schedule.get('steps') or []:
        pool = _find_pool(st.get('pool_id'))
        missing.update(f for f in (pool or {}).get('files', []) if f not in files_with_ts)
    return sorted(missing)

@app.route('/api/schedules', methods=['GET'])
def list_schedules():
    config.load_config()
    schedules = config.get('schedules', []) or []
    return jsonify({'schedules': [dict(s, missing_timestamps=_schedule_warnings(s)) for s in schedules]})

@app.route('/api/schedules', methods=['POST'])
def create_schedule():
    config.load_config()
    data = request.get_json() or {}
    data.setdefault('steps', [])
    if not data['steps']:
        # Placeholder so an empty schedule can be created and then filled in
        first = (config.get('greeting_pools', []) or [None])[0]
        if not first:
            return jsonify({'error': 'Create a pool first'}), 400
        data['steps'] = [{'at': '00:00', 'pool_id': first['id']}]
    fields, err = _clean_schedule(data)
    if err:
        return jsonify({'error': err}), 400
    schedule = dict(fields, id=str(uuid.uuid4()))
    config.set('schedules', (config.get('schedules', []) or []) + [schedule])
    config.save_config()
    return jsonify({'success': True, 'schedule': schedule})

@app.route('/api/schedules/<schedule_id>', methods=['PUT'])
def update_schedule(schedule_id):
    config.load_config()
    schedule = sched.get_schedule(config, schedule_id)
    if not schedule:
        return jsonify({'error': 'Schedule not found'}), 404
    fields, err = _clean_schedule(request.get_json() or {})
    if err:
        return jsonify({'error': err}), 400
    schedule.update(fields)
    config.save_config()
    return jsonify({'success': True, 'schedule': schedule})

@app.route('/api/schedules/<schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    config.load_config()
    if not sched.get_schedule(config, schedule_id):
        return jsonify({'error': 'Schedule not found'}), 404
    config.set('schedules', [s for s in config.get('schedules', []) or []
                             if str(s.get('id')) != str(schedule_id)])
    ref = sched.schedule_ref(schedule_id)
    assignments = config.get('sensor_pools', {}) or {}
    for port in list(assignments):
        if assignments[port] == ref:
            assignments[port] = ''
    config.set('sensor_pools', assignments)
    for t in config.get('network_triggers', []) or []:
        if t.get('pool_id') == ref:
            t['pool_id'] = ''
    _disable_timed_triggers_using(ref)
    config.save_config()
    return jsonify({'success': True})

@app.route('/api/schedule/status', methods=['GET'])
def schedule_status():
    config.load_config()
    clock = sched.clock_state(config)
    labels = {'synced': 'Synced', 'manual': 'Set manually', 'test': 'TEST', 'unset': 'Clock not set'}
    ports = []
    for port in SENSOR_PORTS:
        ref = (config.get('sensor_pools', {}) or {}).get(port)
        if not sched.is_schedule_ref(ref):
            continue
        cur = sched.resolve(config, sched.schedule_id_from_ref(ref))
        if not cur:
            continue
        pool = _find_pool(cur['pool_id'])
        ports.append({'port': port, 'schedule': cur['schedule'].get('name'),
                      'pool': pool.get('name') if pool else None,
                      'step_at': cur['step'].get('at'), 'next_at': cur['next'],
                      'reason': cur['reason']})
    return jsonify({
        'time': clock['now'].strftime('%Y-%m-%d %H:%M:%S'),
        'clock_state': clock['state'], 'clock_label': labels[clock['state']],
        'test_time': config.get('schedule_test_time') or '',
        'override_active': (config.get('schedule_override') or {}).get('step') is not None,
        'ports': ports,
    })

@app.route('/api/schedule/advance', methods=['POST'])
def schedule_advance():
    config.load_config()
    if not sched.advance_assigned(config):
        return jsonify({'error': 'No schedule is assigned to a sensor port'}), 400
    return jsonify({'success': True})

@app.route('/api/schedule/auto', methods=['POST'])
def schedule_auto():
    config.load_config()
    sched.set_override(config, None, None)
    return jsonify({'success': True})

@app.route('/api/schedule/test_time', methods=['POST'])
def schedule_test_time():
    """Set (or clear, with '') a fake local time: {test_time: 'YYYY-MM-DDTHH:MM'}"""
    config.load_config()
    value = ((request.get_json() or {}).get('test_time') or '').strip()
    if value:
        try:
            datetime.fromisoformat(value)
        except ValueError:
            return jsonify({'error': 'Invalid date/time'}), 400
    config.set('schedule_test_time', value)
    config.save_config()
    return jsonify({'success': True})

@app.route('/api/schedule/clock', methods=['POST'])
def schedule_set_clock():
    """Set the Pi's clock: {epoch: seconds} (phone time) or {datetime: 'YYYY-MM-DDTHH:MM'}
    (read as the Pi's local time)."""
    data = request.get_json() or {}
    try:
        if data.get('epoch') is not None:
            epoch = int(data['epoch'])
        else:
            epoch = int(datetime.fromisoformat(data['datetime']).timestamp())
    except (ValueError, KeyError, TypeError):
        return jsonify({'error': 'Provide epoch or datetime'}), 400
    if not sched.set_system_clock(epoch):
        return jsonify({'error': 'Could not set the clock (is the sudoers entry for `date` installed?)'}), 500
    return jsonify({'success': True})

# --- TIMED TRIGGERS API ---

def _clean_timed_trigger(data):
    """Validate a timed trigger body. Returns (fields, error)."""
    if sched.parse_hhmm(data.get('time')) is None:
        return None, 'Invalid time (use HH:MM)'
    audio_file = data.get('audio_file') or ''
    pool_id = data.get('pool_id') or ''
    if bool(audio_file) == bool(pool_id):
        return None, 'Choose what to play'
    if audio_file and audio_file not in audio_controller.list_audio_files():
        return None, 'Audio file not found'
    if pool_id and not _valid_ref(pool_id):
        return None, 'Invalid pool'
    active_date = (data.get('active_date') or '').strip()
    if active_date:
        try:
            datetime.strptime(active_date, '%Y-%m-%d')
        except ValueError:
            return None, 'Active date must be YYYY-MM-DD'
    return {'name': (data.get('name') or '').strip() or 'Timed Trigger',
            'time': data['time'], 'audio_file': audio_file, 'pool_id': pool_id,
            'active_date': active_date, 'enabled': bool(data.get('enabled', True))}, None

def _timed_target_label(t):
    if t.get('audio_file'):
        return (config.get('audio_descriptions', {}) or {}).get(t['audio_file']) or t['audio_file']
    ref = t.get('pool_id')
    if sched.is_schedule_ref(ref):
        sc = sched.get_schedule(config, sched.schedule_id_from_ref(ref))
        return 'Schedule: ' + sc['name'] if sc else None
    pool = _find_pool(ref)
    return 'Pool: ' + pool['name'] if pool else None

@app.route('/api/timed_triggers', methods=['GET'])
def list_timed_triggers():
    config.load_config()
    clock = sched.clock_state(config)
    state = timed.load_state(config)
    items = []
    for t in config.get('timed_triggers', []) or []:
        status = timed.evaluate(t, clock['now'], state)
        items.append(dict(t, status=status['status'], status_at=status.get('at'),
                          in_minutes=status.get('in_minutes'), target=_timed_target_label(t)))
    # One chronological view of the night: announcements and pool-schedule steps together
    timeline = []
    for t in config.get('timed_triggers', []) or []:
        if t.get('enabled', True) and timed.due_minutes(t) is not None:
            timeline.append({'at': t['time'], 'kind': 'announce', 'label': t.get('name'),
                             'detail': _timed_target_label(t), 'date': t.get('active_date') or '',
                             'sort': timed.due_minutes(t)})
    for sc in config.get('schedules', []) or []:
        for st in sc.get('steps') or []:
            pool = _find_pool(st.get('pool_id'))
            timeline.append({'at': st.get('at'), 'kind': 'switch', 'label': sc.get('name'),
                             'detail': pool['name'] if pool else None, 'date': sc.get('active_date') or '',
                             'sort': sched.step_minutes(st, sc)})
    timeline.sort(key=lambda e: e['sort'])
    labels = {'synced': 'Synced', 'manual': 'Set manually', 'test': 'TEST', 'unset': 'Clock not set'}
    return jsonify({'triggers': items, 'timeline': timeline,
                    'clock_state': clock['state'], 'clock_label': labels[clock['state']],
                    'clock_trusted': clock['trusted'], 'time': clock['now'].strftime('%H:%M'),
                    'wait_limit': timed.WAIT_LIMIT_MINUTES})

@app.route('/api/timed_triggers', methods=['POST'])
def create_timed_trigger():
    config.load_config()
    fields, err = _clean_timed_trigger(request.get_json() or {})
    if err:
        return jsonify({'error': err}), 400
    trigger = dict(fields, id=str(uuid.uuid4()))
    config.set('timed_triggers', (config.get('timed_triggers', []) or []) + [trigger])
    config.save_config()
    return jsonify({'success': True, 'trigger': trigger})

@app.route('/api/timed_triggers/<trigger_id>', methods=['PUT'])
def update_timed_trigger(trigger_id):
    config.load_config()
    trigger = next((t for t in config.get('timed_triggers', []) or []
                    if str(t.get('id')) == str(trigger_id)), None)
    if not trigger:
        return jsonify({'error': 'Timed trigger not found'}), 404
    fields, err = _clean_timed_trigger(request.get_json() or {})
    if err:
        return jsonify({'error': err}), 400
    trigger.update(fields)
    config.save_config()
    return jsonify({'success': True, 'trigger': trigger})

@app.route('/api/timed_triggers/<trigger_id>', methods=['DELETE'])
def delete_timed_trigger(trigger_id):
    config.load_config()
    triggers = config.get('timed_triggers', []) or []
    if not any(str(t.get('id')) == str(trigger_id) for t in triggers):
        return jsonify({'error': 'Timed trigger not found'}), 404
    config.set('timed_triggers', [t for t in triggers if str(t.get('id')) != str(trigger_id)])
    config.save_config()
    return jsonify({'success': True})

@app.route('/api/timed_triggers/<trigger_id>/run', methods=['POST'])
def run_timed_trigger(trigger_id):
    """Play it now, as a test. Does not mark it done for tonight."""
    config.load_config()
    t = next((t for t in config.get('timed_triggers', []) or []
              if str(t.get('id')) == str(trigger_id)), None)
    if not t:
        return jsonify({'success': False, 'message': 'Timed trigger not found'}), 404
    body = {'audio_file': t['audio_file']} if t.get('audio_file') else {'pool_id': t.get('pool_id')}
    return jsonify(_controller_post('play', body))

# --- SHOWS API ---

def _show_json(show, active_id):
    is_active = str(show.get('id')) == str(active_id)
    return {'id': show['id'], 'name': show.get('name'), 'active': is_active,
            'modified': shows_lib.is_modified(config, show) if is_active else False,
            'summary': shows_lib.summary(config, show.get('snapshot') or {})}

@app.route('/api/shows', methods=['GET'])
def list_shows():
    config.load_config()
    active = config.get('active_show')
    if active and not shows_lib.get_show(config, active):
        active = None
    return jsonify({'shows': [_show_json(s, active) for s in config.get('shows', []) or []],
                    'active_show': active or ''})

@app.route('/api/shows', methods=['POST'])
def create_show():
    """Save the current settings as a new show, and make it the active one."""
    config.load_config()
    name = ((request.get_json() or {}).get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Give the show a name'}), 400
    if any((s.get('name') or '').lower() == name.lower() for s in config.get('shows', []) or []):
        return jsonify({'error': 'A show with that name already exists'}), 400
    live = shows_lib.capture(config)
    show = {'id': str(uuid.uuid4()), 'name': name, 'snapshot': live}
    # The new show gets its own timed trigger ids; the live ones keep theirs. Switch the
    # live config to the new copy so the two stay identical and show as unmodified.
    show['snapshot'] = shows_lib.fresh_ids(live)
    config.set('shows', (config.get('shows', []) or []) + [show])
    config.set('timed_triggers', copy.deepcopy(show['snapshot']['timed_triggers']))
    config.set('active_show', show['id'])
    config.save_config()
    return jsonify({'success': True, 'show': _show_json(show, show['id'])})

@app.route('/api/shows/<show_id>', methods=['PUT'])
def update_show(show_id):
    """Rename, or save the current settings into this show ({save: true})."""
    config.load_config()
    show = shows_lib.get_show(config, show_id)
    if not show:
        return jsonify({'error': 'Show not found'}), 404
    data = request.get_json() or {}
    if data.get('name') is not None:
        name = data['name'].strip()
        if not name:
            return jsonify({'error': 'Give the show a name'}), 400
        if any(s is not show and (s.get('name') or '').lower() == name.lower() for s in config.get('shows', []) or []):
            return jsonify({'error': 'A show with that name already exists'}), 400
        show['name'] = name
    if data.get('save'):
        if str(config.get('active_show')) != str(show_id):
            return jsonify({'error': 'Switch to this show before saving changes to it'}), 400
        show['snapshot'] = shows_lib.capture(config)
    config.save_config()
    return jsonify({'success': True})

@app.route('/api/shows/<show_id>/activate', methods=['POST'])
def activate_show(show_id):
    config.load_config()
    show = shows_lib.get_show(config, show_id)
    if not show:
        return jsonify({'error': 'Show not found'}), 404
    warnings = shows_lib.apply(config, show.get('snapshot') or {}, audio_controller.list_audio_files())
    config.set('active_show', show['id'])
    config.save_config()
    return jsonify({'success': True, 'warnings': warnings})

@app.route('/api/shows/<show_id>', methods=['DELETE'])
def delete_show(show_id):
    config.load_config()
    if not shows_lib.get_show(config, show_id):
        return jsonify({'error': 'Show not found'}), 404
    config.set('shows', [s for s in config.get('shows', []) or [] if str(s.get('id')) != str(show_id)])
    if str(config.get('active_show')) == str(show_id):
        config.set('active_show', '')   # the live settings stay as they are, just unsaved
    config.save_config()
    return jsonify({'success': True})

# --- NETWORK TRIGGERS MANAGEMENT API ---

@app.route('/api/network_triggers', methods=['GET'])
def list_network_triggers():
    triggers = config.get('network_triggers', []) or []
    # Hide secrets in listing; expose presence only
    redacted = []
    for t in triggers:
        redacted.append({
            'id': t.get('id'),
            'name': t.get('name'),
            'audio_file': t.get('audio_file'),
            'pool_id': t.get('pool_id') or '',
            'action': t.get('action') or 'play',
            'enabled': t.get('enabled', True),
            'secret_present': bool(t.get('secret'))
        })
    trigger_port = config.get('network_trigger.port', 5055)
    return jsonify({'triggers': redacted, 'port': trigger_port})

@app.route('/api/network_triggers', methods=['POST'])
def create_network_trigger():
    data = request.get_json()
    name = data.get('name') or 'New Trigger'
    audio_file = data.get('audio_file')
    secret = (data.get('secret') or '').strip()
    enabled = bool(data.get('enabled', True))
    pool_id = data.get('pool_id') or ''
    action = data.get('action') or 'play'
    if action not in TRIGGER_ACTIONS:
        return jsonify({'error': 'Invalid action'}), 400
    if pool_id and not _valid_ref(pool_id):
        return jsonify({'error': 'Invalid pool_id'}), 400
    if action == 'play' and (not audio_file or audio_file not in audio_controller.list_audio_files()):
        return jsonify({'error': 'Invalid or missing audio_file'}), 400
    new_trigger = {
        'id': str(uuid.uuid4()),
        'name': name,
        'audio_file': audio_file,
        'pool_id': pool_id,
        'action': action,
        'secret': secret,
        'enabled': enabled
    }
    triggers = config.get('network_triggers', []) or []
    triggers.append(new_trigger)
    config.set('network_triggers', triggers)
    config.save_config()
    return jsonify({'success': True, 'trigger': {k: v for k, v in new_trigger.items() if k != 'secret'}})

@app.route('/api/network_triggers/<trigger_id>', methods=['PUT'])
def update_network_trigger(trigger_id):
    data = request.get_json()
    triggers = config.get('network_triggers', []) or []
    for t in triggers:
        if str(t.get('id')) == str(trigger_id):
            if 'name' in data:
                t['name'] = data.get('name') or t.get('name')
            if 'audio_file' in data and (data.get('action') or t.get('action') or 'play') == 'play':
                af = data.get('audio_file')
                if af and af in audio_controller.list_audio_files():
                    t['audio_file'] = af
                else:
                    return jsonify({'error': 'Invalid audio_file'}), 400
            if 'pool_id' in data:
                pid = data.get('pool_id') or ''
                if pid and not _valid_ref(pid):
                    return jsonify({'error': 'Invalid pool_id'}), 400
                t['pool_id'] = pid
            if 'action' in data:
                if data.get('action') not in TRIGGER_ACTIONS:
                    return jsonify({'error': 'Invalid action'}), 400
                t['action'] = data.get('action')
            if 'enabled' in data:
                t['enabled'] = bool(data.get('enabled'))
            if 'secret' in data:
                t['secret'] = (data.get('secret') or '').strip()
            config.set('network_triggers', triggers)
            config.save_config()
            rt = dict(t)
            rt.pop('secret', None)
            return jsonify({'success': True, 'trigger': rt})
    return jsonify({'error': 'Trigger not found'}), 404

@app.route('/api/network_triggers/<trigger_id>', methods=['DELETE'])
def delete_network_trigger(trigger_id):
    triggers = config.get('network_triggers', []) or []
    new_list = [t for t in triggers if str(t.get('id')) != str(trigger_id)]
    if len(new_list) == len(triggers):
        return jsonify({'error': 'Trigger not found'}), 404
    config.set('network_triggers', new_list)
    config.save_config()
    return jsonify({'success': True})

@app.route('/api/network_triggers/<trigger_id>/fire', methods=['POST'])
def fire_network_trigger(trigger_id):
    # Proxy to local trigger server to avoid CORS and unify auth
    triggers = config.get('network_triggers', []) or []
    trig = next((t for t in triggers if str(t.get('id')) == str(trigger_id)), None)
    if not trig or not trig.get('enabled', True):
        return jsonify({'error': 'Trigger not found'}), 404
    port = config.get('network_trigger.port', 5055)
    url = f'http://127.0.0.1:{port}/api/trigger/{trigger_id}/play'
    headers = {}
    secret = (trig.get('secret') or '').strip()
    if secret:
        headers['Authorization'] = f'Bearer {secret}'
    try:
        resp = requests.post(url, headers=headers, timeout=5)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        app.logger.error(f"Proxy fire failed: {e}")
        return jsonify({'error': 'Failed to fire trigger'}), 500

if __name__ == '__main__':
    app.run(host=config.get('web.host', '0.0.0.0'), 
            port=config.get('web.port', 8000), 
            debug=config.get('web.debug', True))
