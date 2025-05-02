"""
Module for managing WiFi configuration storage.
The WiFi configuration is stored in a file on the root of the ESP32.
"""

import os
import ujson

# File to store the WiFi configuration
CONFIG_FILE = "wifi_config.json"

def save_config(config):
    """Save the WiFi configuration to a file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            ujson.dump(config, f)
        return True
    except Exception as e:
        print(f"Error saving WiFi config: {e}")
        return False

def load_config():
    """Load the WiFi configuration from a file."""
    try:
        # Check if the file exists
        if CONFIG_FILE in os.listdir():
            with open(CONFIG_FILE, 'r') as f:
                config = ujson.load(f)
                return config
    except Exception as e:
        print(f"Error loading WiFi config: {e}")
    
    # Return default configuration if file doesn't exist or error occurs
    return {
        "ssid": "",
        "password": "",
        "server_host": "",
        "server_port": 12345
    }

def is_configured():
    """Check if the WiFi is configured."""
    config = load_config()
    return bool(config.get("ssid", ""))

def get_server_info():
    """Get the server information from the configuration."""
    config = load_config()
    # The server port is now the TCP port provided by the unified server
    # The server_port in the config is the port where the unified server is running
    # The actual TCP port for device connection is provided separately
    return {
        "host": config.get("server_host", ""),
        "port": config.get("tcp_port", 12345)  # Use tcp_port if available, otherwise fallback to default
    }
