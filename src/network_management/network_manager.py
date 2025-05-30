# Import the function and constants from ap_mode_manager
from .ap_mode_manager import switch_to_client_mode as ap_manager_switch_to_client_mode
from .ap_mode_manager import AP_CONNECTION_NAME as DEFAULT_AP_NAME
from .ap_mode_manager import AP_IP_ADDRESS as DEFAULT_AP_IP_CIDR

import subprocess
import logging
import shlex

logger = logging.getLogger(__name__)

class NetworkManager:
    def _run_nmcli_command(self, command_list, use_sudo=True):
        try:
            prefix = ['sudo'] if use_sudo else []
            full_command = prefix + ['nmcli'] + command_list
            logger.debug(f"Running command: {' '.join(shlex.quote(str(arg)) for arg in full_command)}")
            result = subprocess.run(full_command, capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                error_message = result.stderr.strip() if result.stderr else result.stdout.strip()
                # Common non-fatal errors for delete/add/up
                if ("not found" in error_message.lower() or \
                    "unknown connection" in error_message.lower() or \
                    "already active" in error_message.lower()):
                    logger.warning(f"nmcli info (potentially non-fatal): {error_message} for command {' '.join(command_list)}")
                    # For connect 'already active' is a success
                    if "already active" in error_message.lower() and command_list[0:2] == ['connection', 'up']:
                         return True, "Connection already active."
                    return False, error_message 
                logger.error(f"nmcli error: {error_message} for command {' '.join(command_list)}")
                return False, error_message
            return True, result.stdout.strip()
        except FileNotFoundError:
            logger.error(f"Error: 'nmcli' or 'sudo' command not found. Ensure they are installed and in PATH.")
            return False, "nmcli or sudo command not found"
        except Exception as e:
            logger.error(f"Error running subprocess: {e} for command {' '.join(command_list)}")
            return False, str(e)

    def scan_wifi_networks(self):
        # Ensure device wifi rescan happens
        self._run_nmcli_command(['device', 'wifi', 'rescan'])
        success, output = self._run_nmcli_command(['-t', '-f', 'SSID,SECURITY,SIGNAL', 'device', 'wifi', 'list', '--rescan', 'yes'])
        networks = []
        if success and output:
            seen_ssids = set()
            for line in output.split('\n'):
                if line:
                    parts = line.strip().split(':')
                    if len(parts) >= 1: # SSID is mandatory
                        ssid = parts[0]
                        if not ssid or ssid in seen_ssids: # Skip empty or duplicate SSIDs
                            continue
                        seen_ssids.add(ssid)
                        security = parts[1] if len(parts) > 1 and parts[1] else 'Open'
                        signal = parts[2] if len(parts) > 2 and parts[2] else '0'
                        networks.append({'ssid': ssid, 'security': security, 'signal': int(signal)})
            networks.sort(key=lambda x: x['signal'], reverse=True)
        return networks

    def get_saved_networks(self):
        success, output = self._run_nmcli_command(['-t', '-f', 'NAME,UUID,TYPE', 'connection', 'show'])
        saved_networks = []
        if success and output:
            for line in output.split('\n'):
                if line:
                    parts = line.strip().split(':')
                    if len(parts) == 3 and parts[2] == '802-11-wireless':
                        # Exclude the AP mode network if named 'ghosthost' or 'zoltar' (from reference)
                        if parts[0].lower() not in ['ghosthost', 'zoltar', 'psychic']:
                             saved_networks.append({'name': parts[0], 'uuid': parts[1]})
        return saved_networks

    def connect_network(self, ssid_or_uuid, password=None):
        is_ap_active, _ = self.get_ap_mode_status()
        if is_ap_active:
            logger.info(f"AP mode is active. Calling ap_mode_manager.switch_to_client_mode for SSID: {ssid_or_uuid}")
            # This function now handles bringing down AP, deleting profile, and connecting.
            success = ap_manager_switch_to_client_mode(target_ssid=ssid_or_uuid, target_password=password)
            if success:
                return True, f"Successfully switched from AP mode and connected to {ssid_or_uuid}"
            else:
                return False, f"Failed to switch from AP mode or connect to {ssid_or_uuid}"
        else:
            # Standard connection logic when not in AP mode
            logger.info(f"Not in AP mode. Attempting to connect to {ssid_or_uuid}")
            # Try connecting to an existing saved connection first by SSID (name) or UUID
            # Use use_sudo=True for nmcli connection up
            success, msg = self._run_nmcli_command(['connection', 'up', ssid_or_uuid], use_sudo=True)
            if success:
                if "Connection activation failed" not in msg: # A bit of a heuristic for real success
                    logger.info(f"Successfully connected to existing connection: {ssid_or_uuid}")
                    return True, msg
                else:
                    logger.warning(f"'nmcli connection up {ssid_or_uuid}' reported success but message indicates failure: {msg}")
                    # Fall through to try with password if provided
            
            # If it failed (maybe not a saved connection, or needs password) and password is provided, try connect with password
            if password and ssid_or_uuid: # ssid_or_uuid here must be an SSID
                logger.info(f"Trying to connect to {ssid_or_uuid} with password (will create/update profile).")
                # nmcli dev wifi connect will create a profile or update if one with the same SSID exists.
                # It's generally preferred over manual add+up for simple cases.
                # Ensure use_sudo=True
                connect_command = ['device', 'wifi', 'connect', ssid_or_uuid, 'password', password]
                # Optionally add 'name' field to create a connection with a specific name based on SSID
                # connect_command.extend(['name', ssid_or_uuid])
                success, msg = self._run_nmcli_command(connect_command, use_sudo=True)
                if success:
                    logger.info(f"Successfully initiated connection to {ssid_or_uuid} with new/updated profile.")
                else:
                    logger.error(f"Failed to connect to {ssid_or_uuid} with password: {msg}")
                return success, msg
            
            logger.error(f"Failed to connect to {ssid_or_uuid}. It might not be a saved connection or requires a password not provided. Last message: {msg}")
            return False, msg

    def save_network(self, ssid, password, autoconnect=True):
        connection_name = ssid # Use SSID as connection name by default
        
        # Delete existing connection with the same name to ensure fresh settings
        self._run_nmcli_command(['connection', 'delete', connection_name])

        cmd = [
            'connection', 'add',
            'type', 'wifi',
            'con-name', connection_name,
            'ifname', 'wlan0', # Assuming wlan0, make configurable if necessary
            'ssid', ssid,
            'wifi-sec.key-mgmt', 'wpa-psk', # Assuming WPA/WPA2 PSK
            'wifi-sec.psk', password,
            'connection.autoconnect', 'yes' if autoconnect else 'no'
        ]
            
        success, msg = self._run_nmcli_command(cmd)
        if success:
            logger.info(f"Network {ssid} saved successfully with autoconnect: {autoconnect}.")
        else:
            logger.error(f"Failed to save network {ssid}: {msg}")
        return success, msg

    def delete_network(self, name_or_uuid):
        success, msg = self._run_nmcli_command(['connection', 'delete', name_or_uuid])
        if success:
            logger.info(f"Network {name_or_uuid} deleted successfully.")
        else:
            logger.error(f"Failed to delete network {name_or_uuid}: {msg}")
        return success, msg

    def get_current_ssid(self):
        success, output = self._run_nmcli_command(['-t', '-f', 'ACTIVE,SSID', 'device', 'wifi'])
        if success and output:
            for line in output.split('\n'):
                if line.startswith('yes:'):
                    return line.split(':')[1]
        return None

    def get_active_connection_details(self):
        # Get active connection name(s)
        success, output = self._run_nmcli_command(['-t', '-f', 'NAME,TYPE,DEVICE', 'connection', 'show', '--active'])
        active_wifi_connection = None
        if success and output:
            for line in output.strip().split('\n'):
                parts = line.split(':')
                if len(parts) == 3 and parts[1] == '802-11-wireless' and parts[2].startswith('wlan'): # check interface
                    active_wifi_connection = parts[0] # NAME
                    break
        
        if active_wifi_connection:
            success, details_output = self._run_nmcli_command(['-t', 'connection', 'show', active_wifi_connection])
            if success and details_output:
                details = {}
                for detail_line in details_output.strip().split('\n'):
                    if ':' in detail_line:
                        key, value = detail_line.split(':', 1)
                        details[key.strip()] = value.strip()
                return details
        return None

    def disconnect_network(self, name_or_uuid=None):
        if name_or_uuid:
            success, msg = self._run_nmcli_command(['connection', 'down', name_or_uuid])
        else: # Disconnect the active wifi connection on wlan0
            active_details = self.get_active_connection_details()
            if active_details and active_details.get('GENERAL.NAME'):
                success, msg = self._run_nmcli_command(['connection', 'down', active_details['GENERAL.NAME']])
            else:
                return False, "No active WiFi connection found to disconnect."
        
        if success:
            logger.info(f"Connection {name_or_uuid if name_or_uuid else 'active wlan0'} brought down successfully.")
        else:
            logger.error(f"Failed to bring down connection {name_or_uuid if name_or_uuid else 'active wlan0'}: {msg}")
        return success, msg

    def get_ap_mode_status(self):
        """Checks if the system is currently in the defined AP mode."""
        active_details = self.get_active_connection_details()
        ap_ip_base = DEFAULT_AP_IP_CIDR.split('/')[0]
        if active_details:
            conn_name = active_details.get('GENERAL.NAME', '')
            ip4_address_full = active_details.get('IP4.ADDRESS[1]', '') # e.g., '192.168.42.1/24'
            ip4_address = ip4_address_full.split('/')[0] if '/' in ip4_address_full else ''
            interface_name = active_details.get('GENERAL.INTERFACE', '')

            logger.debug(f"get_ap_mode_status: Conn Name: {conn_name}, IP: {ip4_address}, Interface: {interface_name}")
            logger.debug(f"Comparing with AP Name: {DEFAULT_AP_NAME}, AP IP: {ap_ip_base}")

            if conn_name == DEFAULT_AP_NAME and ip4_address == ap_ip_base and interface_name == 'wlan0': # Assuming wlan0 for AP
                 logger.info(f"AP mode is active: {DEFAULT_AP_NAME} on {ip4_address}")
                 return True, DEFAULT_AP_NAME
        logger.debug("AP mode is not active or details do not match.")
        return False, None

# Removed activate_ap_mode and deactivate_ap_mode methods as requested.
# The button-based ap_mode_manager.py now handles activation.
# The connect_network method, when called in AP mode, will use 
# ap_mode_manager.switch_to_client_mode to deactivate AP and connect to client Wi-Fi. 