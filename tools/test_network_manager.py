# tools/test_network_manager.py
import sys
from pathlib import Path
import logging

# Add project root to sys.path to allow importing NetworkManager
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.network_management.network_manager import NetworkManager

# Configure logging to see debug messages from NetworkManager
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def main():
    nm = NetworkManager()
    print("NetworkManager Test CLI")
    print("-----------------------")

    while True:
        print("\nAvailable actions:")
        print("  1. Scan WiFi Networks")
        print("  2. List Saved Networks")
        print("  3. Connect to Network (SSID/UUID, optionally with password)")
        print("  4. Save Network (SSID, password, autoconnect)")
        print("  5. Delete Network (Name/UUID)")
        print("  6. Get Current SSID")
        print("  7. Disconnect Network (Name/UUID or active)")
        print("  8. Activate AP Mode")
        print("  9. Deactivate AP Mode")
        print(" 10. Get AP Mode Status")
        print(" 11. Get Active Connection Details")
        print("  0. Exit")

        choice = input("Enter your choice: ")

        try:
            if choice == '1':
                print("Scanning...")
                networks = nm.scan_wifi_networks()
                print("Available Networks:")
                if networks:
                    for net in networks:
                        print(f"  SSID: {net['ssid']}, Security: {net['security']}, Signal: {net['signal']}")
                else:
                    print("  No networks found or error during scan.")
            
            elif choice == '2':
                print("Listing saved networks...")
                saved = nm.get_saved_networks()
                print("Saved Networks:")
                if saved:
                    for net in saved:
                        print(f"  Name: {net['name']}, UUID: {net['uuid']}")
                else:
                    print("  No saved networks found.")

            elif choice == '3':
                ssid_or_uuid = input("Enter SSID or UUID to connect: ").strip()
                password = input("Enter password (leave blank if none or already saved): ").strip()
                password = password if password else None
                print(f"Connecting to {ssid_or_uuid}...")
                success, msg = nm.connect_network(ssid_or_uuid, password)
                print(f"Result: {'Success' if success else 'Failed'}. Message: {msg}")

            elif choice == '4':
                ssid = input("Enter SSID to save: ").strip()
                password = input("Enter password: ").strip()
                if not password:
                    print("Password cannot be empty for saving a new network.")
                    continue
                autoconnect_str = input("Autoconnect? (yes/no) [yes]: ").strip().lower()
                autoconnect = autoconnect_str != 'no'
                print(f"Saving {ssid}...")
                success, msg = nm.save_network(ssid, password, autoconnect)
                print(f"Result: {'Success' if success else 'Failed'}. Message: {msg}")

            elif choice == '5':
                name_or_uuid = input("Enter Name or UUID to delete: ").strip()
                print(f"Deleting {name_or_uuid}...")
                success, msg = nm.delete_network(name_or_uuid)
                print(f"Result: {'Success' if success else 'Failed'}. Message: {msg}")

            elif choice == '6':
                print("Getting current SSID...")
                ssid = nm.get_current_ssid()
                print(f"Current SSID: {ssid if ssid else 'Not Connected'}")

            elif choice == '7':
                name_or_uuid = input("Enter Name or UUID to disconnect (leave blank for active): ").strip()
                name_or_uuid = name_or_uuid if name_or_uuid else None
                print(f"Disconnecting {name_or_uuid if name_or_uuid else 'active connection'}...")
                success, msg = nm.disconnect_network(name_or_uuid)
                print(f"Result: {'Success' if success else 'Failed'}. Message: {msg}")
            
            elif choice == '8':
                print("Activating AP mode (using defaults: ghosthost, ghosthostap)...")
                success, msg = nm.activate_ap_mode()
                print(f"Result: {'Success' if success else 'Failed'}. Message: {msg}")

            elif choice == '9':
                print("Deactivating AP mode (using default: ghosthost)...")
                success, msg = nm.deactivate_ap_mode()
                print(f"Result: {'Success' if success else 'Failed'}. Message: {msg}")

            elif choice == '10':
                print("Getting AP mode status...")
                active, ap_ssid = nm.get_ap_mode_status()
                if active:
                    print(f"AP Mode is ACTIVE. SSID: {ap_ssid}")
                else:
                    print("AP Mode is INACTIVE.")
            
            elif choice == '11':
                print("Getting active connection details...")
                details = nm.get_active_connection_details()
                if details:
                    print("Active Connection Details:")
                    for key, value in details.items():
                        print(f"  {key}: {value}")
                else:
                    print("  No active WiFi connection or details found.")

            elif choice == '0':
                print("Exiting.")
                break
            else:
                print("Invalid choice. Please try again.")
        except Exception as e:
            print(f"An error occurred during the operation: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main() 