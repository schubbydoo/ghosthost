# Ghost Host Animatronic System

A Raspberry Pi-based animatronic control system that provides synchronized audio, motor movements, and LED effects triggered by various sensors.

## Features

- **Sensor Integration**: PIR motion sensors, push button, and pressure pad
- **Motor Control**: Head, torso, and mouth motors with synchronized movements
- **Audio Playback**: Synchronized mouth movement with word timestamps
- **LED Eyes**: Dynamic eye lighting with various effects
- **Web Interface**: Configuration and file management via web UI
- **Network Management**: WiFi configuration with AP mode fallback

## Hardware Requirements

### Raspberry Pi Setup
- Raspberry Pi Zero 2W (or compatible)
- MicroSD card (16GB+ recommended)
- Power supply (5V, 2.5A minimum)

### Motors and Drivers
- 3x DC Motors (head, torso, mouth)
- 2x DRV8833 Motor Driver Modules
- Motor mounting hardware and gearing

### Sensors
- 2x PIR Motion Sensors (left/right detection)
- 1x Push Button Switch
- 1x Pressure Sensor/Foot Pad

### Other Components
- LEDs for eyes
- Speakers for audio output
- Resistors and connecting wires
- Breadboard or PCB for connections

## GPIO Pin Assignments

| GPIO | Function               | Component          |
|------|------------------------|--------------------|
| 15   | LED Eyes               | LED Output         |
| 9    | PIR Left Sensor        | Sensor Input       |
| 25   | PIR Right Sensor       | Sensor Input       |
| 21   | Push Button            | Sensor Input       |
| 20   | Pressure Pad           | Sensor Input       |
| 4    | Head Motor IN1         | DRV8833 #1         |
| 14   | Head Motor IN2         | DRV8833 #1         |
| 17   | Torso Motor IN1        | DRV8833 #1         |
| 18   | Torso Motor IN2        | DRV8833 #1         |
| 22   | Mouth Motor IN1        | DRV8833 #2         |
| 23   | Mouth Motor IN2        | DRV8833 #2         |

## Installation

### 1. System Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3-venv python3-pip git alsa-utils

# Clone the repository
git clone <repository-url> ghosthost
cd ghosthost

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy and edit configuration file
cp config/default_config.yaml config/config.yaml

# Edit GPIO pins if needed
nano config/config.yaml
```

### 3. Audio Setup

```bash
# Test audio output
speaker-test -t sine -f 1000 -l 1

# Set audio volume (0-100)
amixer sset PCM 80%
```

### 4. Service Installation (Optional)

```bash
# Create systemd service
sudo cp scripts/ghosthost.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ghosthost
sudo systemctl start ghosthost
```

## Usage

### Starting the System

```bash
# Manual start
cd ghosthost
source venv/bin/activate
python main.py

# Or if service is installed
sudo systemctl start ghosthost
```

### Motor Testing

Use the motor testing tool to calibrate motor durations:

```bash
cd tools
python motor_test_tool.py
```

This interactive tool helps you:
- Test individual motors
- Determine optimal mouth open duration
- Measure head/torso rotation timing
- Calibrate movement parameters

### Audio File Management

1. **Adding Audio Files**:
   - Place `.wav` files in the `SoundFiles/` directory
   - Generate timestamps using: `python generate_word_timestamps.py`

2. **Setting Default Audio**:
   - Edit `config/config.yaml`
   - Set `audio.default_file` to your chosen file

### Web Interface

Access the web interface at `http://ghosthost.local:8000` for:
- Volume control
- Cooldown period configuration
- Audio file selection
- File upload/management
- WiFi configuration

### Network Configuration

**Automatic WiFi Connection**:
- Edit `config/config.yaml` to set your WiFi credentials
- Or use the web interface

**AP Mode Activation**:
- Hold the button for 10 seconds
- Connect to "ghosthost" network (no password)
- Navigate to 192.168.4.1 for configuration

## Operation Modes

### Sensor Triggers

1. **Motion Detection**:
   - PIR sensors detect movement
   - Head/torso rotate toward detected direction
   - Audio plays with synchronized mouth movement
   - Eyes light up during performance

2. **Button Press**:
   - Short press triggers performance
   - Long press (10s) activates AP mode

3. **Pressure Pad**:
   - Step trigger activates performance
   - Same behavior as button press

### Performance Sequence

1. Sensor detects trigger
2. Eyes light up immediately
3. Audio playback begins
4. Head/torso motors start rotating
5. Mouth moves in sync with audio timestamps
6. All effects end when audio completes
7. Cooldown period begins (configurable duration)

## Configuration

### Main Settings (`config/config.yaml`)

```yaml
# Audio Settings
audio:
  default_file: "HMGreeting.wav"
  volume: 80
  soundfiles_dir: "SoundFiles"

# Sensor Settings
sensors:
  debounce_time: 0.2        # seconds
  cooldown_period: 30       # seconds after performance

# Motor Settings
motors:
  head_torso_duration: 0    # 0 = full audio duration
  mouth_open_duration: 0.1  # seconds per word
  mouth_close_delay: 0.05   # pause between words
```

### GPIO Customization

Edit the `hardware.gpio` section in config to match your wiring.

## Troubleshooting

### Common Issues

**Audio not playing**:
```bash
# Check audio devices
aplay -l

# Test audio output
speaker-test -t sine -f 1000 -l 1

# Check volume
amixer sget PCM
```

**Motors not responding**:
```bash
# Check GPIO permissions
sudo usermod -a -G gpio $USER

# Test individual motors
cd tools
python motor_test_tool.py
```

**Sensors not triggering**:
```bash
# Check sensor status via web interface
# Or check logs
tail -f logs/ghosthost.log
```

**WiFi connection issues**:
```bash
# Check network status
nmcli device status

# Restart networking
sudo systemctl restart NetworkManager

# Check available networks
nmcli device wifi list
```

### Log Files

Monitor system logs:
```bash
# Real-time log monitoring
tail -f logs/ghosthost.log

# System service logs
sudo journalctl -u ghosthost -f
```

### Hardware Testing

**Test individual components**:
```bash
# Motor testing
cd tools && python motor_test_tool.py

# LED testing (in Python)
from src.hardware.led_controller import LEDController
from src.core.config_manager import config
led = LEDController(config)
led.test_eyes()
led.cleanup()
```

## Development

### Project Structure

```
ghosthost/
├── src/
│   ├── core/              # Core system modules
│   ├── hardware/          # Hardware controllers
│   ├── network/           # Network management
│   └── web/               # Web interface
├── config/                # Configuration files
├── SoundFiles/            # Audio files and timestamps
├── tools/                 # Testing and utility scripts
├── logs/                  # Application logs
└── docs/                  # Documentation
```

### Adding New Features

1. **New Sensor Types**: Extend `SensorManager` class
2. **Motor Behaviors**: Modify `MotorController` class
3. **Audio Effects**: Enhance `AudioController` class
4. **Web Features**: Add routes in `src/web/`

### Testing

```bash
# Run unit tests (when available)
python -m pytest tests/

# Manual hardware testing
cd tools
python motor_test_tool.py
```

## Safety Notes

- **Motor Safety**: Ensure proper motor mounting to prevent mechanical damage
- **Power Requirements**: Use adequate power supply for motors and Pi
- **GPIO Protection**: Consider using protection resistors on GPIO pins
- **Emergency Stop**: Always have a way to quickly power down the system

## License

This project is released under the MIT License. See LICENSE file for details.

## Support

For questions and support:
- Check the troubleshooting section above
- Review log files in `logs/ghosthost.log`
- Use the motor testing tools for hardware validation
- Access the web interface for real-time status # ghosthost
