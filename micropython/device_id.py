"""
Module for managing the device ID (MAC address) storage.
The device ID is stored in a file on the root of the ESP32.
"""

import os
import network
import ubinascii

# File to store the device ID
DEVICE_ID_FILE = "device_id.txt"

def get_mac_address():
    """Get the MAC address of the ESP32 WiFi interface."""
    wlan = network.WLAN(network.STA_IF)
    mac = ubinascii.hexlify(wlan.config('mac')).decode('utf-8')
    # Format MAC address with colons (AA:BB:CC:DD:EE:FF)
    formatted_mac = ':'.join(mac[i:i+2] for i in range(0, len(mac), 2)).upper()
    return formatted_mac

def save_device_id(device_id=None):
    """Save the device ID to a file."""
    if device_id is None:
        device_id = get_mac_address()
    
    with open(DEVICE_ID_FILE, 'w') as f:
        f.write(device_id)
    
    return device_id

def load_device_id():
    """Load the device ID from a file or generate a new one if not found."""
    try:
        # Check if the file exists
        if DEVICE_ID_FILE in os.listdir():
            with open(DEVICE_ID_FILE, 'r') as f:
                device_id = f.read().strip()
                if device_id:
                    return device_id
    except:
        pass
    
    # If we get here, either the file doesn't exist or is empty
    # Generate and save a new device ID
    return save_device_id()
