import RPi.GPIO as GPIO
import time
import subprocess
import logging
import shlex # For quoting arguments if needed, though direct list is often safer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# GPIO settings
AP_MODE_SWITCH_PIN = 21
PRESS_DURATION_FOR_AP_MODE = 10  # seconds

# NetworkManager settings
AP_CONNECTION_NAME = "GhostHostAP"  # Name for the AP connection profile in NetworkManager
AP_SSID = "GhostHost_Setup"
AP_IP_ADDRESS = "192.168.4.1/24"  # Static IP for the Pi in AP mode
AP_INTERFACE_NAME = "wlan0" # Typically wlan0 for Raspberry Pi Wi-Fi
NMCLI_CMD = ["sudo", "nmcli"] # Centralize sudo and nmcli command

# Store the last known client Wi-Fi connection
LAST_CLIENT_CONNECTION_UUID = None
LAST_CLIENT_CONNECTION_NAME = None

def _run_nmcli_command(args_list, check=True):
    """Helper to run nmcli commands with sudo."""
    try:
        command = NMCLI_CMD + args_list
        logging.debug(f"Running command: {' '.join(shlex.quote(str(arg)) for arg in command)}")
        result = subprocess.run(command, capture_output=True, text=True, check=check)
        if check and result.returncode != 0: # check=True handles this, but for explicit logging
            logging.error(f"nmcli error for command {' '.join(args_list)}: {result.stderr.strip() or result.stdout.strip()}")
        return result
    except FileNotFoundError:
        logging.error(f"Error: '{NMCLI_CMD[0]}' or '{NMCLI_CMD[1]}' command not found. Is it installed and in PATH?")
        raise # Re-raise to be caught by calling function
    except subprocess.CalledProcessError as e:
        logging.error(f"CalledProcessError for nmcli command {' '.join(args_list)}: {e.stderr.strip() or e.stdout.strip()}")
        raise # Re-raise

def get_active_wifi_connection():
    """Gets the name and UUID of the current active Wi-Fi connection."""
    try:
        # No check=True here, as we parse output and handle no active connection gracefully
        result = _run_nmcli_command(["-t", "-f", "NAME,UUID,TYPE", "connection", "show", "--active"], check=False)
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                parts = line.split(':')
                # Ensure we have enough parts and it's a wifi connection
                if len(parts) >= 3 and ("wifi" in parts[2].lower() or "802-11-wireless" in parts[2].lower()):
                    name, uuid = parts[0], parts[1]
                    # Avoid identifying the AP itself as a client connection
                    if name != AP_CONNECTION_NAME:
                        return name, uuid
        else:
            logging.warning(f"Could not get active Wi-Fi connection: {result.stderr.strip() or result.stdout.strip()}")
    except Exception as e: # Catch FileNotFoundError or CalledProcessError from _run_nmcli_command
        logging.error(f"Exception in get_active_wifi_connection: {e}")
    return None, None

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(AP_MODE_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    logging.info(f"GPIO {AP_MODE_SWITCH_PIN} set up for AP mode switch.")

def switch_to_ap_mode():
    global LAST_CLIENT_CONNECTION_NAME, LAST_CLIENT_CONNECTION_UUID
    logging.info("Switching to AP mode...")

    # Get current connection *before* attempting to bring anything down
    current_name, current_uuid = get_active_wifi_connection()
    if current_name and current_uuid:
        LAST_CLIENT_CONNECTION_NAME, LAST_CLIENT_CONNECTION_UUID = current_name, current_uuid
        logging.info(f"Current active Wi-Fi client: {LAST_CLIENT_CONNECTION_NAME} (UUID: {LAST_CLIENT_CONNECTION_UUID})")
        try:
            _run_nmcli_command(["connection", "down", LAST_CLIENT_CONNECTION_UUID])
            logging.info(f"Disconnected from {LAST_CLIENT_CONNECTION_NAME}.")
        except subprocess.CalledProcessError as e:
            # If it's already down or doesn't exist, that's fine for AP mode setup.
            logging.warning(f"Could not disconnect from {LAST_CLIENT_CONNECTION_NAME} (may already be down): {e}")
        except FileNotFoundError: # from _run_nmcli_command
            return False # nmcli not available
    else:
        logging.info("No active client Wi-Fi connection found, or unable to determine it. Proceeding to AP setup.")
        # Reset them if no connection was found, so we don't try to restore a stale one
        LAST_CLIENT_CONNECTION_NAME, LAST_CLIENT_CONNECTION_UUID = None, None


    try:
        # Check if AP connection profile already exists
        show_result = _run_nmcli_command(["-t", "-f", "NAME", "connection", "show"], check=False)
        ap_profile_exists = False
        if show_result.returncode == 0 and AP_CONNECTION_NAME in show_result.stdout:
            ap_profile_exists = True
        
        if ap_profile_exists:
            logging.info(f"AP connection profile '{AP_CONNECTION_NAME}' already exists. Bringing it up.")
            _run_nmcli_command(["connection", "up", AP_CONNECTION_NAME])
        else:
            logging.info(f"Creating and starting AP connection profile: {AP_CONNECTION_NAME}")
            _run_nmcli_command([
                "connection", "add", "type", "wifi", "ifname", AP_INTERFACE_NAME,
                "con-name", AP_CONNECTION_NAME, "autoconnect", "no", # Don't autoconnect AP mode
                "ssid", AP_SSID, "mode", "ap",
                "ipv4.method", "shared", # Provides DHCP to clients
                "ip4", AP_IP_ADDRESS, # Set static IP for the AP itself
                # No gateway needed for 'shared' ipv4.method as it implies NAT
            ])
            _run_nmcli_command(["connection", "modify", AP_CONNECTION_NAME, "wifi-sec.key-mgmt", "wpa-psk"])
            _run_nmcli_command(["connection", "modify", AP_CONNECTION_NAME, "wifi-sec.psk", "ghosthost"]) # Default password "ghosthost"
            # No need to modify ipv4.method to shared again if set during add
            
            logging.info(f"Bringing up AP connection '{AP_CONNECTION_NAME}'...")
            _run_nmcli_command(["connection", "up", AP_CONNECTION_NAME])

        logging.info(f"AP mode activated. SSID: {AP_SSID}, IP: {AP_IP_ADDRESS.split('/')[0]}")
        logging.info(f"Connect to SSID '{AP_SSID}' (password: ghosthost) and navigate to http://{AP_IP_ADDRESS.split('/')[0]}:8000 for Wi-Fi setup.") # Assuming port 8000 from web_interface/app.py
        return True

    except subprocess.CalledProcessError as e:
        logging.error(f"Error during AP mode activation: {e}")
        return False
    except FileNotFoundError: # from _run_nmcli_command
        logging.error("nmcli command not found during AP mode activation.")
        return False

def switch_to_client_mode(target_ssid=None, target_password=None):
    logging.info("Attempting to switch to client mode...")
    try:
        # Bring down the AP mode connection if it's active
        # Check if AP_CONNECTION_NAME is active on AP_INTERFACE_NAME
        active_con_result = _run_nmcli_command(["-t", "-f", "NAME,DEVICE", "connection", "show", "--active"], check=False)
        ap_is_active_on_interface = False
        if active_con_result.returncode == 0:
            for line in active_con_result.stdout.strip().split('\n'):
                if AP_CONNECTION_NAME in line and AP_INTERFACE_NAME in line:
                    ap_is_active_on_interface = True
                    break
        
        if ap_is_active_on_interface:
            logging.info(f"AP mode '{AP_CONNECTION_NAME}' is active. Bringing it down.")
            _run_nmcli_command(["connection", "down", AP_CONNECTION_NAME], check=False) # Don't fail if already down
        else:
            logging.info(f"AP mode '{AP_CONNECTION_NAME}' not found active on {AP_INTERFACE_NAME}.")

        # Delete the AP connection profile to ensure clean switch-over
        show_con_result = _run_nmcli_command(["-t", "-f", "NAME", "connection", "show"], check=False)
        if show_con_result.returncode == 0 and AP_CONNECTION_NAME in show_con_result.stdout:
            logging.info(f"Deleting AP connection profile: {AP_CONNECTION_NAME}")
            _run_nmcli_command(["connection", "delete", AP_CONNECTION_NAME])
        else:
            logging.info(f"AP connection profile '{AP_CONNECTION_NAME}' not found, no need to delete.")


        if target_ssid and target_password:
            logging.info(f"Connecting to specified Wi-Fi network: {target_ssid}")
            # Use nmcli device wifi connect. This command automatically creates/updates a connection.
            # It's generally robust. No need to manually delete old profiles with the same SSID unless specific issues arise.
            # nmcli dev wifi connect <ssid> password <password> ifname <ifname> name <profile_name_if_desired>
            connect_cmd = ["device", "wifi", "connect", target_ssid, "password", target_password, "ifname", AP_INTERFACE_NAME]
            # Optionally, give the new connection a specific name:
            # connect_cmd.extend(["name", f"Client_{target_ssid}"])
            
            # Before connecting, rescan can be helpful
            _run_nmcli_command(["device", "wifi", "rescan", "ifname", AP_INTERFACE_NAME], check=False)
            time.sleep(3) # Give rescan a moment

            connection_result = _run_nmcli_command(connect_cmd, check=False) # check=False to handle output manually
            
            if connection_result.returncode == 0:
                logging.info(f"Successfully initiated connection to {target_ssid}.")
                # Verify connection status after attempting
                time.sleep(10) # Wait for connection to establish
                new_name, new_uuid = get_active_wifi_connection()
                if new_name == target_ssid or (new_name and target_ssid in new_name): # Sometimes name gets a suffix
                    logging.info(f"Connection to {target_ssid} confirmed active.")
                    LAST_CLIENT_CONNECTION_NAME, LAST_CLIENT_CONNECTION_UUID = new_name, new_uuid
                    return True
                else:
                    logging.warning(f"Connection to {target_ssid} initiated but could not confirm active status. Current active: {new_name}")
                    # Fall through to fallback if available
            else:
                logging.error(f"Failed to connect to {target_ssid}. Error: {connection_result.stderr.strip() or connection_result.stdout.strip()}")
                # Fallback logic continues below if this fails

        # Fallback or reconnect to last known connection
        if LAST_CLIENT_CONNECTION_UUID:
            logging.info(f"Attempting to reconnect to the last known Wi-Fi: {LAST_CLIENT_CONNECTION_NAME} (UUID: {LAST_CLIENT_CONNECTION_UUID})")
            # Check if the profile still exists
            show_res = _run_nmcli_command(["-t", "-f", "UUID", "connection", "show"], check=False)
            if show_res.returncode == 0 and LAST_CLIENT_CONNECTION_UUID in show_res.stdout:
                fallback_result = _run_nmcli_command(["connection", "up", LAST_CLIENT_CONNECTION_UUID], check=False)
                if fallback_result.returncode == 0:
                    logging.info(f"Successfully reconnected to {LAST_CLIENT_CONNECTION_NAME}.")
                    return True
                else:
                    logging.error(f"Failed to reconnect to {LAST_CLIENT_CONNECTION_NAME}: {fallback_result.stderr.strip() or fallback_result.stdout.strip()}")
            else:
                logging.warning(f"Last known connection profile {LAST_CLIENT_CONNECTION_NAME} (UUID {LAST_CLIENT_CONNECTION_UUID}) no longer exists.")
                LAST_CLIENT_CONNECTION_NAME, LAST_CLIENT_CONNECTION_UUID = None, None # Clear stale info
        else:
            logging.warning("No target SSID provided and no last known client connection to restore.")
        
        return False # If all attempts fail

    except subprocess.CalledProcessError as e:
        logging.error(f"Error switching to client mode: {e}")
        return False
    except FileNotFoundError: # from _run_nmcli_command
        logging.error("nmcli command not found during client mode switch.")
        return False

def main_loop():
    setup_gpio()
    button_pressed_time = None
    in_ap_mode = False # Track if we are currently in AP mode triggered by this script

    # Initial check for AP mode (e.g., if script restarts while AP is already active)
    try:
        active_connections_result = _run_nmcli_command(["-t", "-f", "NAME,DEVICE", "connection", "show", "--active"], check=False)
        if active_connections_result.returncode == 0:
            for line in active_connections_result.stdout.strip().split('\n'):
                if AP_CONNECTION_NAME in line and AP_INTERFACE_NAME in line:
                    logging.info(f"Script started/restarted. Device already in AP mode ('{AP_CONNECTION_NAME}').")
                    in_ap_mode = True
                    break
    except Exception as e:
        logging.warning(f"Could not determine initial network state or nmcli not ready during startup: {e}")


    logging.info("AP Mode Manager started. Press and hold the button for 10 seconds to activate AP mode.")
    if in_ap_mode:
        logging.info("Currently in AP mode. Web server should provide config page. Button press will not trigger AP mode again while in this state.")


    while True:
        current_time = time.time()
        button_state = GPIO.input(AP_MODE_SWITCH_PIN)

        if button_state == GPIO.LOW:  # Button pressed
            if button_pressed_time is None:
                button_pressed_time = current_time
                logging.debug("AP mode button pressed.")
            # Check for hold duration ONLY if not already in AP mode
            elif not in_ap_mode and (current_time - button_pressed_time) >= PRESS_DURATION_FOR_AP_MODE:
                logging.info(f"Button held for {PRESS_DURATION_FOR_AP_MODE} seconds. Activating AP mode.")
                if switch_to_ap_mode():
                    in_ap_mode = True 
                    logging.info("AP mode activated. This script will now wait for network configuration via web UI to switch back.")
                else:
                    logging.error("Failed to switch to AP mode. Button press monitoring will continue.")
                button_pressed_time = None # Reset timer regardless of success to prevent immediate re-trigger
        else:  # Button not pressed or released
            if button_pressed_time is not None:
                if not in_ap_mode : # Only log release if we weren't trying to activate AP mode
                     logging.debug("AP mode button released before duration or action taken.")
                button_pressed_time = None # Reset timer

        if in_ap_mode:
            # Periodically check if we are still in AP mode.
            # If not, it means the web UI (or another process) has switched network.
            # This check should be fairly lightweight.
            if current_time % 15 < 0.1 : # Check roughly every 15 seconds
                try:
                    is_still_ap = False
                    active_check_result = _run_nmcli_command(["-t", "-f", "NAME,DEVICE", "connection", "show", "--active"], check=False)
                    if active_check_result.returncode == 0:
                        for line in active_check_result.stdout.strip().split('\n'):
                            if AP_CONNECTION_NAME in line and AP_INTERFACE_NAME in line:
                                is_still_ap = True
                                break
                    if not is_still_ap:
                        logging.info("Detected switch from AP mode (likely by web UI). Resuming normal button monitoring for AP activation.")
                        in_ap_mode = False
                        # Update last known connection as it might have changed
                        LAST_CLIENT_CONNECTION_NAME, LAST_CLIENT_CONNECTION_UUID = get_active_wifi_connection()
                        if LAST_CLIENT_CONNECTION_NAME:
                            logging.info(f"Now connected to: {LAST_CLIENT_CONNECTION_NAME}")
                        else:
                            logging.info("Now in client mode, but not connected to any Wi-Fi.")
                except Exception as e:
                    logging.warning(f"Error checking AP status while in AP mode: {e}")


        time.sleep(0.1) # Polling interval

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        logging.info("AP Mode Manager stopped by user.")
    finally:
        GPIO.cleanup()
        logging.info("GPIO cleanup done.") 