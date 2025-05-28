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
        # Try connecting to an existing saved connection first by SSID (name) or UUID
        success, msg = self._run_nmcli_command(['connection', 'up', ssid_or_uuid])
        if success:
            logger.info(f"Successfully connected to existing connection: {ssid_or_uuid}")
            return True, msg
        
        # If it failed (maybe not a saved connection, or needs password) and password is provided, try connect with password
        if password and ssid_or_uuid: # ssid_or_uuid here must be an SSID
            logger.info(f"Trying to connect to {ssid_or_uuid} with password.")
            # Delete if a failed/incomplete connection exists with this name to avoid conflicts
            self._run_nmcli_command(['connection', 'delete', ssid_or_uuid]) 
            success, msg = self._run_nmcli_command(['device', 'wifi', 'connect', ssid_or_uuid, 'password', password])
            if success:
                logger.info(f"Successfully connected to {ssid_or_uuid} with new connection.")
            else:
                logger.error(f"Failed to connect to {ssid_or_uuid} with password: {msg}")
            return success, msg
        
        logger.error(f"Failed to connect to {ssid_or_uuid}. Last message: {msg}")
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
            logger.info(f"Network {ssid} saved successfully.")
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
        # Check if 'ghosthost' or 'zoltar' AP connection is active
        active_details = self.get_active_connection_details()
        if active_details and active_details.get('GENERAL.NAME', '').lower() in ['ghosthost', 'zoltar', 'psychic']:
            if active_details.get('IP4.ADDRESS[1]', '').startswith('192.168.4.1'): # Typical AP IP
                 return True, active_details.get('GENERAL.NAME')
        return False, None

    def activate_ap_mode(self, ap_name="ghosthost", password="ghosthostap", ip_address="192.168.4.1/24", channel=6):
        logger.info(f"Attempting to activate AP mode: {ap_name}")

        # 1. Bring down any existing wlan0 connection
        self.disconnect_network() # Disconnects current active on wlan0

        # 2. Delete existing AP connection if it exists to ensure fresh settings
        self._run_nmcli_command(['connection', 'delete', ap_name])

        # 3. Create new AP mode connection
        ap_cmd = [
            'connection', 'add',
            'type', 'wifi',
            'con-name', ap_name,
            'ifname', 'wlan0',
            'mode', 'ap',
            'ssid', ap_name,
            '802-11-wireless.band', 'bg',
            '802-11-wireless.channel', str(channel),
            'wifi-sec.key-mgmt', 'wpa-psk',
            'wifi-sec.psk', password,
            'ipv4.method', 'shared', # Use 'shared' for NAT/DHCP for clients
            'ipv4.addresses', ip_address
        ]
        # 'ipv4.method', 'manual',
        # 'ipv4.addresses', ip_address,
        # 'ipv4.gateway', '192.168.4.1' # Gateway is the AP itself

        success_add, msg_add = self._run_nmcli_command(ap_cmd)
        if not success_add:
            logger.error(f"Failed to add AP connection {ap_name}: {msg_add}")
            return False, f"Failed to add AP connection: {msg_add}"

        # 4. Bring up the AP connection
        # Short delay to ensure connection is saved before trying to bring it up
        import time
        time.sleep(2)
        success_up, msg_up = self._run_nmcli_command(['connection', 'up', ap_name])
        if success_up:
            logger.info(f"AP mode '{ap_name}' activated successfully.")
            return True, f"AP mode '{ap_name}' activated."
        else:
            logger.error(f"Failed to bring up AP connection {ap_name}: {msg_up}")
            # Clean up by deleting the failed AP connection
            self._run_nmcli_command(['connection', 'delete', ap_name])
            return False, f"Failed to bring up AP connection: {msg_up}"

    def deactivate_ap_mode(self, ap_name="ghosthost"):
        logger.info(f"Attempting to deactivate AP mode: {ap_name}")
        # Bring down and delete the AP connection
        success_down, msg_down = self._run_nmcli_command(['connection', 'down', ap_name])
        success_del, msg_del = self._run_nmcli_command(['connection', 'delete', ap_name])
        
        if success_down or "not found" in str(msg_down).lower() or "unknown connection" in str(msg_down).lower():
            logger.info(f"AP mode '{ap_name}' deactivated (or was not active).")
            # Optionally, try to bring up a general autoconnect wifi connection
            # This is a bit speculative, might need specific logic to choose which one
            self._run_nmcli_command(['connection', 'up', 'default'], use_sudo=True) # Or iterate saved connections
            return True, f"AP mode '{ap_name}' deactivated."
        else:
            logger.error(f"Failed to deactivate AP mode {ap_name}: {msg_down} / {msg_del}")
            return False, f"Failed to deactivate AP: {msg_down}" 