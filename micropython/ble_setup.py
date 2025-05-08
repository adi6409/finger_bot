"""
Module for handling Bluetooth Low Energy (BLE) functionality for device setup.
This module provides a BLE server that allows the device to be configured via a mobile app.

The BLE server provides the following functionality:
1. Advertising the device for discovery
2. Handling connections from a central device (e.g., mobile app)
3. Receiving and processing commands for device configuration
4. Scanning and connecting to WiFi networks
"""

import ubluetooth
import ujson
import network
import time
import sys
from micropython import const

# BLE Service and Characteristic UUIDs
_ESP32_SERVICE_UUID = ubluetooth.UUID('4fafc201-1fb5-459e-8fcc-c5c9c331914b')
_ESP32_CHAR_UUID = ubluetooth.UUID('beb5483e-36e1-4688-b7f5-ea07361b26a8')

# BLE Constants
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
_IRQ_GATTS_READ_REQUEST = const(4)

# WiFi station interface
_wlan = network.WLAN(network.STA_IF)
_wlan.active(True)

# Constants
MAX_WIFI_CONNECT_WAIT = 20  # Maximum seconds to wait for WiFi connection

class BLESetup:
    """
    BLE Setup class for device configuration via Bluetooth
    
    This class handles BLE advertising, connections, and command processing
    for device setup and configuration.
    """
    
    def __init__(self, name="ESP32-Setup"):
        """
        Initialize the BLE setup
        
        Args:
            name: Device name for BLE advertising
        """
        try:
            self._ble = ubluetooth.BLE()
            self._ble.active(True)
            self._ble.irq(self._irq)
            self._register_services()
            
            # Connection tracking
            self._connections = set()
            self._write_callback = None
            self._payload = None
            self._name = name
            
            # Configuration state
            self._config = {}
            self._buffer = b''  # Buffer for accumulating partial JSON data
            self._device_registered = False  # Flag to track device registration
            
            # Start advertising
            self._advertise(name)
            
            print(f"BLE setup initialized with name: {name}")
        except Exception as e:
            print(f"Error initializing BLE: {e}")
            sys.print_exception(e)
        
    def _irq(self, event, data):
        """
        BLE event handler
        
        Args:
            event: BLE event type
            data: Event data
        """
        try:
            # Handle connection events
            if event == _IRQ_CENTRAL_CONNECT:
                conn_handle, _, _ = data
                self._connections.add(conn_handle)
                print("BLE: Central connected")
                self._buffer = b''  # Clear buffer on new connection
                
            elif event == _IRQ_CENTRAL_DISCONNECT:
                conn_handle, _, _ = data
                if conn_handle in self._connections:
                    self._connections.remove(conn_handle)
                print("BLE: Central disconnected")
                # Clear buffer on disconnect
                self._buffer = b''
                
                # Only try to re-advertise if we're still in setup mode
                try:
                    # Start advertising again after disconnect, but only if BLE is still active
                    if self._ble.active():
                        self._advertise(self._name)
                except Exception as e:
                    print(f"Error re-advertising after disconnect: {e}")
                
            # Handle data write events
            elif event == _IRQ_GATTS_WRITE:
                conn_handle, value_handle = data
                if conn_handle in self._connections and value_handle == self._handle:
                    self._handle_data_write(conn_handle, value_handle)
                    
            # Handle read request events
            elif event == _IRQ_GATTS_READ_REQUEST:
                conn_handle, value_handle = data
                if conn_handle in self._connections and value_handle == self._handle:
                    if self._payload:
                        self._ble.gatts_write(self._handle, self._payload)
        except Exception as e:
            print(f"Error in BLE IRQ handler: {e}")
            sys.print_exception(e)
    
    def _handle_data_write(self, conn_handle, value_handle):
        """
        Handle data written to the characteristic
        
        Args:
            conn_handle: Connection handle
            value_handle: Value handle
        """
        try:
            # Read the data from the characteristic
            data_received = self._ble.gatts_read(self._handle)
            
            # Accumulate data in buffer
            self._buffer += data_received
            
            # Print the current buffer for debugging
            print(f"Buffer now contains: {self._buffer}")
            
            # Check if we have a complete JSON object by looking for closing brace
            if b'}' in self._buffer:
                try:
                    # Try to parse the buffer as JSON
                    buffer_str = self._buffer.decode()
                    # Find the position of the last closing brace
                    last_brace_pos = buffer_str.rfind('}')
                    # Extract the complete JSON string
                    complete_json_str = buffer_str[:last_brace_pos+1]
                    
                    # Validate by parsing
                    test_json = ujson.loads(complete_json_str)
                    
                    print(f"Complete JSON received: {complete_json_str}")
                    
                    # If we get here, we have valid JSON
                    if self._write_callback:
                        self._write_callback(complete_json_str.encode())
                    else:
                        self._payload = complete_json_str.encode()
                    
                    # Clear buffer after successful processing
                    self._buffer = b''
                except ValueError as e:
                    # If we get a ValueError, the JSON might still be incomplete
                    # Keep the data in the buffer for the next chunk
                    print(f"JSON parsing error: {e}")
                    print(f"Accumulated partial data: {self._buffer}")
            else:
                # No closing brace yet, keep accumulating
                print(f"Accumulated partial data (waiting for complete JSON): {self._buffer}")
        except Exception as e:
            print(f"Error handling data write: {e}")
            sys.print_exception(e)
    
    def _register_services(self):
        """Register GATT services and characteristics"""
        try:
            # Register GATT server with service and characteristic
            services = (
                (_ESP32_SERVICE_UUID, (
                    (_ESP32_CHAR_UUID, ubluetooth.FLAG_WRITE | ubluetooth.FLAG_READ | ubluetooth.FLAG_NOTIFY,),
                ),),
            )
            ((self._handle,),) = self._ble.gatts_register_services(services)
            print("BLE services registered successfully")
        except Exception as e:
            print(f"Error registering BLE services: {e}")
            sys.print_exception(e)
            raise  # Re-raise to abort initialization
    
    def _advertise(self, name):
        """
        Start BLE advertising
        
        Args:
            name: Device name to advertise
        """
        try:
            self._name = name
            # Advertise with the device name
            # 0x02, 0x01, 0x06: Length, Type (Flags), Value (LE General Discoverable)
            # len(name) + 1, 0x09: Length, Type (Complete Local Name)
            adv_data = bytearray(b'\x02\x01\x06') + bytearray((len(name) + 1, 0x09)) + name.encode()
            self._ble.gap_advertise(100, adv_data)  # 100ms interval
            print(f"BLE: Advertising as {name}")
        except Exception as e:
            print(f"Error in advertising: {e}")
            sys.print_exception(e)
    
    def send_response(self, response):
        """
        Send a response to the connected client
        
        Args:
            response: Response data (dict, str, or bytes)
        """
        try:
            # Convert response to bytes if needed
            if isinstance(response, dict):
                response = ujson.dumps(response)
            if isinstance(response, str):
                response = response.encode()
            
            # Store response and notify all connected clients
            self._payload = response
            for conn_handle in self._connections:
                self._ble.gatts_notify(conn_handle, self._handle, response)
                
            print(f"Response sent: {response[:100]}...")  # Print first 100 bytes
        except Exception as e:
            print(f"Error sending response: {e}")
            sys.print_exception(e)
    
    def set_write_callback(self, callback):
        """
        Set a callback function to be called when data is received
        
        Args:
            callback: Function to call with received data
        """
        self._write_callback = callback
    
    def is_connected(self):
        """
        Check if a client is connected
        
        Returns:
            bool: True if connected, False otherwise
        """
        return len(self._connections) > 0
    
    def scan_wifi_networks(self):
        """
        Scan for available WiFi networks
        
        Returns:
            list: List of SSID strings
        """
        try:
            _wlan.active(True)
            print("Scanning for WiFi networks...")
            networks = _wlan.scan()
            ssids = []
            
            for net in networks:
                try:
                    # net[0] is SSID, net[1] is RSSI, net[2] is authmode, net[3] is channel
                    ssid = net[0].decode('utf-8')
                    if ssid:  # Only add non-empty SSIDs
                        ssids.append(ssid)
                except Exception as e:
                    print(f"Error decoding SSID: {e}")
            
            print(f"Found {len(ssids)} networks: {', '.join(ssids)}")
            return ssids
        except Exception as e:
            print(f"Error scanning WiFi networks: {e}")
            sys.print_exception(e)
            return []
    
    def connect_wifi(self, ssid, password):
        """
        Connect to a WiFi network
        
        Args:
            ssid: Network SSID
            password: Network password
            
        Returns:
            bool: True if connected successfully, False otherwise
        """
        try:
            print(f"Connecting to WiFi: {ssid}")
            _wlan.active(True)
            _wlan.connect(ssid, password)
            
            # Wait for connection with timeout
            for i in range(MAX_WIFI_CONNECT_WAIT):
                if _wlan.isconnected():
                    print(f"Connected to WiFi: {ssid}")
                    return True
                print(f"Connecting to WiFi... ({i+1}/{MAX_WIFI_CONNECT_WAIT})")
                time.sleep(1)
            
            print(f"Failed to connect to WiFi: {ssid}")
            return False
        except Exception as e:
            print(f"Error connecting to WiFi: {e}")
            sys.print_exception(e)
            return False
    
    def get_wifi_status(self):
        """
        Get the current WiFi connection status
        
        Returns:
            dict: WiFi status information
        """
        try:
            if _wlan.isconnected():
                return {
                    "connected": True,
                    "ip": _wlan.ifconfig()[0],
                    "ssid": _wlan.config("essid")
                }
            else:
                return {"connected": False}
        except Exception as e:
            print(f"Error getting WiFi status: {e}")
            sys.print_exception(e)
            return {"connected": False, "error": str(e)}
    
    def process_command(self, data):
        """
        Process a command received from the client
        
        Args:
            data: Command data (bytes or string)
        """
        try:
            # Convert bytes to string if needed
            if isinstance(data, bytes):
                data = data.decode()
            
            print(f"Received command data: {data}")
            
            # Validate and parse JSON
            command = self._parse_command_json(data)
            if not command:
                return
                
            cmd = command.get("command", "")
            print(f"Processing command: {cmd}")
            
            # Handle different commands
            if cmd == "scan_wifi":
                self._handle_scan_wifi_command()
                
            elif cmd == "configure_wifi":
                self._handle_configure_wifi_command(command)
                    
            elif cmd == "get_mac":
                self._handle_get_mac_command()
                
            elif cmd == "get_config":
                self._handle_get_config_command()
                
            elif cmd == "register_device":
                self._handle_register_device_command(command)
                
            else:
                error_msg = {"status": "error", "message": f"Unknown command: {cmd}"}
                print(f"Error: {error_msg}")
                self.send_response(error_msg)
                
        except Exception as e:
            sys.print_exception(e)
            error_msg = {"status": "error", "message": f"Error processing command: {str(e)}"}
            print(f"Exception: {error_msg}")
            self.send_response(error_msg)
    
    def _parse_command_json(self, data):
        """
        Parse and validate JSON command data
        
        Args:
            data: JSON string
            
        Returns:
            dict: Parsed command or None if invalid
        """
        try:
            # Make sure we have a complete JSON object
            if not data.endswith('}'):
                print("Warning: Received potentially incomplete JSON")
                # Find the last complete JSON object
                last_brace_pos = data.rfind('}')
                if last_brace_pos > 0:
                    data = data[:last_brace_pos+1]
                    print(f"Extracted complete JSON: {data}")
                else:
                    error_msg = {"status": "error", "message": "Incomplete JSON data received"}
                    self.send_response(error_msg)
                    return None
            
            # Parse the JSON
            command = ujson.loads(data)
            return command
            
        except ValueError as e:
            print(f"JSON parsing error: {e}")
            error_msg = {"status": "error", "message": f"Invalid JSON format: {str(e)}"}
            self.send_response(error_msg)
            return None
    
    def _handle_scan_wifi_command(self):
        """Handle scan_wifi command"""
        print("Scanning WiFi networks...")
        networks = self.scan_wifi_networks()
        response = {"networks": networks}
        print(f"Sending WiFi networks response: {response}")
        self.send_response(response)
    
    def _handle_configure_wifi_command(self, command):
        """
        Handle configure_wifi command
        
        Args:
            command: Parsed command data
        """
        ssid = command.get("ssid", "")
        password = command.get("password", "")
        server_host = command.get("server_host", "")
        server_port = command.get("server_port", 12345)
        tcp_port = command.get("tcp_port", 443)
        
        print(f"Configuring WiFi: SSID={ssid}, Server={server_host}:{server_port}, TCP Port={tcp_port}")
        
        if not ssid:
            error_msg = {"status": "error", "message": "SSID is required"}
            print(f"Error: {error_msg}")
            self.send_response(error_msg)
            return
        
        # Save configuration
        self._config = {
            "ssid": ssid,
            "password": password,
            "server_host": server_host,
            "server_port": server_port,
            "tcp_port": tcp_port
        }
        
        # Save to persistent storage
        import wifi_config
        wifi_config.save_config(self._config)
        print("WiFi configuration saved to storage")
        
        # Try to connect to WiFi
        print(f"Connecting to WiFi: {ssid}...")
        success = self.connect_wifi(ssid, password)
        
        if success:
            status_msg = {"status": "success", "message": "WiFi configured successfully"}
            print(f"WiFi connected successfully: {_wlan.ifconfig()}")
            self.send_response(status_msg)
        else:
            error_msg = {"status": "error", "message": "Failed to connect to WiFi"}
            print("Failed to connect to WiFi")
            self.send_response(error_msg)
    
    def _handle_get_mac_command(self):
        """Handle get_mac command"""
        print("Getting device MAC address...")
        import device_id
        mac = device_id.get_mac_address()
        response = {"mac": mac}
        print(f"MAC address: {mac}")
        self.send_response(response)
    
    def _handle_get_config_command(self):
        """Handle get_config command"""
        print("Getting current configuration...")
        response = {"config": self._config}
        print(f"Configuration: {self._config}")
        self.send_response(response)
    
    def _handle_register_device_command(self, command):
        """
        Handle register_device command
        
        Args:
            command: Parsed command data
        """
        print("Registering device...")
        device_name = command.get("name", "")
        
        if not device_name:
            error_msg = {"status": "error", "message": "Device name is required"}
            print(f"Error: {error_msg}")
            self.send_response(error_msg)
            return
        
        # Set the device registered flag
        self._device_registered = True
        
        # Send success response
        status_msg = {"status": "success", "message": "Device registered successfully"}
        print("Device registered successfully")
        self.send_response(status_msg)
    
    def start(self):
        """Start the BLE setup service."""
        print("BLE: Setup service started")
        self.set_write_callback(self.process_command)
    
    def stop(self):
        """Stop the BLE setup service."""
        try:
            self._ble.active(False)
            print("BLE: Setup service stopped")
        except Exception as e:
            print(f"Error stopping BLE service: {e}")
            sys.print_exception(e)
