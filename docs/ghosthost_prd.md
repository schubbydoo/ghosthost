# Product Requirements Document (PRD)

## Ghost Host Project for Raspberry Pi

---

## 1. Overview

**Purpose:**
The Ghost Host application runs an animatronic that provides audio output, motorized movements (mouth, head, torso), LED eyes and uses sensors to trigger workflows.

**Baseline Use Cases:**

1. **User approaches from the side:**

   * Animatronic head and torso rotate towards the user (left or right).
   * Animatronic centers position upon opposite sensor detection (user is directly in front).
   * Audio playback and synchronized mouth movement initiate immediately upon detection.
   * Eyes light up upon the sensor trigger.

2. **User presses button:**

   * Animatronic slowly rotates from right to left while playing audio and moving mouth synchronously, simulating crowd engagement.
   * Eyes light up upon the sensor trigger.

3. **User steps on pressure pad:**

   * Same behavior as button press.

---

## 2. Functional Requirements

### 2.1 Sensor Integration

* **Push Button Switch:** Initiates `main.py` execution.
* **Motion Sensor (PIR):** Initiates `main.py` execution.
* **Pressure Sensor (Foot Pad):** Initiates `main.py` execution.

**GPIO Pin Assignments (Raspberry Pi Zero 2W):**

| GPIO | Function               |
| ---- | ---------------------- |
| 15   | LED Eyes               |
| 09   | PIR output - left      |
| 25   | PIR output - right     |
| 14   | DRV8833 #1 IN2 (Head)  |
| 4    | DRV8833 #1 IN1 (Head)  |
| 17   | DRV8833 #1 IN3 (Torso) |
| 18   | DRV8833 #1 IN4 (Torso) |
| 22   | DRV8833 #2 IN1 (Mouth) |
| 23   | DRV8833 #2 IN2 (Mouth) |
| 21   | AP mode switch         |

**GPIO Setup Summary:**

* Pin mode: Input
* Internal pull-up: Enabled
* Signal logic: Active LOW

**Web Interface:**

* Accessible at `ghosthost.local:8000`
* Volume configuration and showing the current setting
* Cooldown period after main.py completes configuration. Should show the current value.
* Choosing the audio file to be played ( in /SoundFiles). This should also include the complimentary .json timestamp file if it exists. If the timestamp .json file does not exist, then A checkbox should be included to automatically have the timestamp .json file created using the /tools/elevenlabs_stt_timestamps.py script. It also should show the current setting. 
* Audio & timestamp file management (upload/delete)
* WiFi network selection and password configuration
* Network configuration section should include the ability to choose from available networks, add/delete from a list of My Networks. See the attached image for reference.

**Network Management:**

* 10-second push of the AP mode switch's button activates AP mode for network configuration.
* Scripts to use NetworkManager cli commands to manage the WIFI connection. 

### 2.2 Event Handling Logic

* Debounce logic for handling simultaneous/sequential sensor triggers.
* Sensors ignored during audio playback with configurable cooldown.

### 2.3 Output and Response

* Audio playback synchronized with mouth movement. (Zoltar project can be referenced)
* Torso/neck directional movement based on trigger event (left/right) if two motion sensors are active. This maybe included in the webUI for identifying that they are indeed being used.

---

## 3. Technical Specifications

### 3.1 Hardware Interface

* The motors are not stepper motors.
* The motor that drives the mouth only goes in a single direction for opening the mouth. It is spring loaded and will automatically close.
* The motors that drive both the head and torso can turn either way for changing direction. The gearing the motor is connected to will allow the head and torso to alternate left and right when the motor continuously rotates in a single direction.


### 3.2 Software Structure

* Modular software architecture (classes/functions).
* Organized directories (network_management, web_interface, SoundFiles, tools, etc.).
* Core modules: NetworkManager, Sensor Manager, Event Handler, Output Controller.
* Use a python virtual environment (i.e., venv)

### 3.3 Dependencies

* Specify versions and provide installation instructions.

### 3.4 Configuration

* Define configuration file structure (YAML, JSON) for sensor settings and behavior.

---

## 5. Implementation Guidelines

### 5.1 Coding Standards

* Follow PEP8 guidelines.
* Detailed comments for readability and maintainability.

### 5.2 Documentation

* Comprehensive README with setup instructions, wiring diagrams, and example configurations.

### 5.3 Testing

* Unit tests for each module.
* Clearly defined integration testing plans.
* Tools should be placed and ran from the /tools directory

## 7. Appendix

* GPIO pin reference, component datasheets, additional references.
