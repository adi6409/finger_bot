"""
Module for handling Bluetooth Low Energy (BLE) functionality for device setup.
This module provides a BLE server that allows the device to be configured via a mobile app.
"""

import ubluetooth
import ujson
import network
import time
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

class BLESetup:
    def __init__(self, name="ESP32-Setup"):
        self._ble = ubluetooth.BLE()
        self._ble.active(True)
        self._ble.irq(self._irq)
        self._register_services()
        self._connections = set()
        self._write_callback = None
        self._payload = None
        self._advertise(name)
        self._config = {}
        self._buffer = b''  # Buffer for accumulating partial JSON data
        
    def _irq(self, event, data):
        # Track connections so we can send notifications
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
            # This prevents errors when the device is transitioning to normal operation
            try:
                # Start advertising again after disconnect, but only if BLE is still active
                if self._ble.active():
                    self._advertise(self._name)
            except OSError as e:
                print(f"Error re-advertising after disconnect: {e}")
                # Don't crash if we can't re-advertise
                pass
            
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            if conn_handle in self._connections and value_handle == self._handle:
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
                    
        elif event == _IRQ_GATTS_READ_REQUEST:
            # Respond to read requests with the current payload
            conn_handle, value_handle = data
            if conn_handle in self._connections and value_handle == self._handle:
                if self._payload:
                    self._ble.gatts_write(self._handle, self._payload)
    
    def _register_services(self):
        # Register GATT server
        services = (
            (_ESP32_SERVICE_UUID, (
                (_ESP32_CHAR_UUID, ubluetooth.FLAG_WRITE | ubluetooth.FLAG_READ | ubluetooth.FLAG_NOTIFY,),
            ),),
        )
        ((self._handle,),) = self._ble.gatts_register_services(services)
    
    def _advertise(self, name):
        try:
            self._name = name
            # Advertise with the device name
            adv_data = bytearray(b'\x02\x01\x06') + bytearray((len(name) + 1, 0x09)) + name.encode()
            self._ble.gap_advertise(100, adv_data)
            print(f"BLE: Advertising as {name}")
        except OSError as e:
            print(f"Error in advertising: {e}")
            # Don't crash if advertising fails
            pass
    
    def send_response(self, response):
        """Send a response to the connected client."""
        if isinstance(response, dict):
            response = ujson.dumps(response)
        if isinstance(response, str):
            response = response.encode()
        
        self._payload = response
        for conn_handle in self._connections:
            self._ble.gatts_notify(conn_handle, self._handle, response)
    
    def set_write_callback(self, callback):
        """Set a callback function to be called when data is received."""
        self._write_callback = callback
    
    def is_connected(self):
        """Check if a client is connected."""
        return len(self._connections) > 0
    
    def scan_wifi_networks(self):
        """Scan for available WiFi networks."""
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
            return []
    
    def connect_wifi(self, ssid, password):
        """Connect to a WiFi network."""
        _wlan.active(True)
        _wlan.connect(ssid, password)
        
        # Wait for connection with timeout
        max_wait = 20
        while max_wait > 0:
            if _wlan.isconnected():
                return True
            max_wait -= 1
            time.sleep(1)
        
        return False
    
    def get_wifi_status(self):
        """Get the current WiFi connection status."""
        if _wlan.isconnected():
            return {
                "connected": True,
                "ip": _wlan.ifconfig()[0],
                "ssid": _wlan.config("essid")
            }
        else:
            return {"connected": False}
    
    def process_command(self, data):
        """Process a command received from the client."""
        try:
            if isinstance(data, bytes):
                data = data.decode()
            
            print(f"Received command data: {data}")
            
            # Validate JSON before processing
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
                        return
                
                command = ujson.loads(data)
                cmd = command.get("command", "")
                print(f"Processing command: {cmd}")
                print(f"Full command data: {command}")
            except ValueError as e:
                print(f"JSON parsing error: {e}")
                error_msg = {"status": "error", "message": f"Invalid JSON format: {str(e)}"}
                self.send_response(error_msg)
                return
            
            if cmd == "scan_wifi":
                print("Scanning WiFi networks...")
                networks = self.scan_wifi_networks()
                response = {"networks": networks}
                print(f"Sending WiFi networks response: {response}")
                self.send_response(response)
                
            elif cmd == "configure_wifi":
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
                    
            elif cmd == "get_mac":
                print("Getting device MAC address...")
                import device_id
                mac = device_id.get_mac_address()
                response = {"mac": mac}
                print(f"MAC address: {mac}")
                self.send_response(response)
                
            elif cmd == "get_config":
                print("Getting current configuration...")
                response = {"config": self._config}
                print(f"Configuration: {self._config}")
                self.send_response(response)
                
            else:
                error_msg = {"status": "error", "message": f"Unknown command: {cmd}"}
                print(f"Error: {error_msg}")
                self.send_response(error_msg)
                
        except Exception as e:
            import sys
            sys.print_exception(e)
            error_msg = {"status": "error", "message": f"Error processing command: {str(e)}"}
            print(f"Exception: {error_msg}")
            self.send_response(error_msg)
    
    def start(self):
        """Start the BLE setup service."""
        print("BLE: Setup service started")
        self.set_write_callback(self.process_command)
    
    def stop(self):
        """Stop the BLE setup service."""
        self._ble.active(False)
        print("BLE: Setup service stopped")
