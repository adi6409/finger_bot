"""
Main module for the ESP32 Finger Bot device.
This module handles the device setup, WiFi connection, and server communication.

The device has the following functionality:
1. Setup mode with BLE for configuration
2. WiFi connection for server communication
3. WebSocket connection for real-time control
4. Servo control for physical button pressing
"""

from machine import Pin, PWM  # type: ignore
import ujson as json
import time
import network  # type: ignore
import machine  # type: ignore
import gc
import sys

# Import custom modules
from single_rgb_utils import set_rgb, blink_rgb_led
import device_id
import wifi_config
import ble_setup

# --- Constants ---
SETUP_BUTTON_PIN = 6      # GPIO0 is often the BOOT button on ESP32 boards
SERVO_PIN = 2             # GPIO2 for servo control
SETUP_MODE_TIMEOUT = 300  # 5 minutes timeout for setup mode
WIFI_CONNECT_TIMEOUT = 20 # 20 seconds timeout for WiFi connection
RECONNECT_DELAY = 5       # 5 seconds delay between reconnection attempts
SERVO_MIN_US = 500        # Minimum pulse width for servo (microseconds)
SERVO_MAX_US = 2400       # Maximum pulse width for servo (microseconds)

# --- LED Status Colors ---
LED_OFF = (0, 0, 0)
LED_BLUE = (0, 0, 255)      # Setup mode / WiFi connected
LED_GREEN = (0, 255, 0)     # Action in progress
LED_CYAN = (0, 255, 255)    # WiFi connected, waiting for registration
LED_RED = (255, 0, 0)       # Error state

# --- Hardware Setup ---
setup_button = Pin(SETUP_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
servo = PWM(Pin(SERVO_PIN), freq=50)  # Standard servo PWM frequency (50Hz)

# --- Global Variables ---
device_mac = None
ble = None
setup_mode = False
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# --- Helper Functions ---

def set_servo_angle(pwm, angle):
    """
    Set angle for SG90 servo: 0 to 180 degrees
    
    Args:
        pwm: PWM object for the servo
        angle: Angle in degrees (0-180)
    """
    us = int(SERVO_MIN_US + (angle / 180) * (SERVO_MAX_US - SERVO_MIN_US))
    duty = int(us * 1024 * 50 / 1000000)  # duty for ESP32 (0-1023 range)
    pwm.duty(duty)

def press():
    """
    Perform the press action with the servo
    
    Returns:
        bool: True if the press action was successful
    """
    try:
        print("Performing press action")
        set_rgb(*LED_GREEN)  # Green for pressed
        
        # Execute the servo movement
        set_servo_angle(servo, 90)  # Rotate to 90 degrees
        time.sleep(0.5)
        set_servo_angle(servo, 0)   # Return to 0 degrees
        time.sleep(0.5)
        
        set_rgb(*LED_OFF)  # Off after pressing
        return True
    except Exception as e:
        print(f"Error during press action: {e}")
        set_rgb(*LED_RED)  # Red for error
        time.sleep(1)
        set_rgb(*LED_OFF)
        return False

def connect_wifi():
    """
    Connect to WiFi using stored credentials
    
    Returns:
        bool: True if connected successfully, False otherwise
    """
    # Check if already connected
    if wlan.isconnected():
        print("Already connected to WiFi")
        return True
    
    # Load WiFi configuration
    try:
        config = wifi_config.load_config()
        ssid = config.get("ssid", "")
        password = config.get("password", "")
        
        if not ssid:
            print("No WiFi configuration found")
            return False
        
        print(f"Connecting to WiFi: {ssid}")
        wlan.connect(ssid, password)
        
        # Wait for connection with timeout
        for i in range(WIFI_CONNECT_TIMEOUT):
            if wlan.isconnected():
                print("Connected to WiFi:", wlan.ifconfig())
                set_rgb(*LED_BLUE)  # Blue for connected
                return True
            
            print(f"Connecting to WiFi... ({i+1}/{WIFI_CONNECT_TIMEOUT})")
            blink_rgb_led(*LED_BLUE, 0.5)  # Blink blue
            time.sleep(1)
        
        print("Failed to connect to WiFi: timeout")
        return False
    except Exception as e:
        print(f"WiFi connection error: {e}")
        return False

def enter_setup_mode():
    """
    Enter device setup mode with BLE advertising
    """
    global setup_mode, ble
    
    print("Entering setup mode")
    setup_mode = True
    set_rgb(*LED_BLUE)  # Blue for setup mode
    
    try:
        # Initialize BLE
        ble = ble_setup.BLESetup(f"ESP32-{device_mac[-6:]}")
        ble.start()
        
        # Variables to track setup progress
        wifi_configured = False
        device_registered = False
        
        # Stay in setup mode for a limited time
        setup_start_time = time.time()
        while setup_mode and (time.time() - setup_start_time < SETUP_MODE_TIMEOUT):
            # Check if WiFi is configured
            if ble._config.get("ssid") and not wifi_configured:
                # Save the WiFi configuration
                wifi_config.save_config(ble._config)
                print("WiFi configuration saved")
                
                # Connect to WiFi in the background
                if connect_wifi():
                    print("WiFi connected successfully")
                    wifi_configured = True
                    
                    # Change LED to indicate WiFi connected but still in setup mode
                    set_rgb(*LED_CYAN)  # Cyan for WiFi connected, waiting for registration
                else:
                    print("Failed to connect to WiFi")
            
            # Check if device is registered
            if ble._device_registered:
                print("Device registered successfully")
                device_registered = True
                setup_mode = False
                break
            
            # Blink LED to indicate setup mode status
            if wifi_configured:
                # Blink cyan if WiFi is configured but device not registered
                blink_rgb_led(*LED_CYAN, 0.5)
            else:
                # Blink blue if in initial setup mode
                blink_rgb_led(*LED_BLUE, 0.5)
                
            time.sleep(0.5)
    except Exception as e:
        print(f"Setup mode error: {e}")
    finally:
        # Exit setup mode
        if ble:
            try:
                ble.stop()
            except Exception as e:
                print(f"Error stopping BLE: {e}")
            ble = None
        
        setup_mode = False
        set_rgb(*LED_OFF)  # Turn off LED
        print("Exiting setup mode")

def check_setup_button():
    """
    Check if the setup button is pressed
    
    Returns:
        bool: True if setup mode was entered, False otherwise
    """
    if not setup_button.value():  # Button is active low
        print("Setup button pressed")
        
        # Wait for button release with debounce
        time.sleep(0.1)
        while not setup_button.value():
            time.sleep(0.1)
        
        # Enter setup mode
        enter_setup_mode()
        return True
    return False

def handle_websocket_message(ws, msg):
    """
    Handle a message received from the WebSocket
    
    Args:
        ws: WebSocket connection
        msg: Message received
        
    Returns:
        bool: True to continue, False to reconnect
    """
    if not msg:
        print("WebSocket closed by server")
        return False
    
    print("Received message:", msg)
    
    try:
        data = json.loads(msg)
        action = data.get("action")
        params = data.get("params", {})
        
        if action == "press":
            print("Executing press action")
            result = press()
            
            # Send result back via WebSocket
            response = {
                "action": "press_result", 
                "params": {"result": result, "timestamp": time.time()}
            }
            ws.send(json.dumps(response))
        elif action == "ping":
            # Respond to ping with pong
            ws.send(json.dumps({"action": "pong", "params": {"timestamp": time.time()}}))
        else:
            print(f"Unknown action: {action}")
    except ValueError as e:
        print(f"Invalid JSON from server: {e}")
    except Exception as e:
        print(f"Error handling message: {e}")
        
    return True

def websocket_loop():
    """
    Main WebSocket communication loop
    """
    try:
        # Import WebSocket library
        import uwebsockets.client
    except ImportError:
        print("uwebsockets.client not found. Please upload uwebsockets library to the device.")
        time.sleep(10)
        return
    
    # Get server information
    server_info = wifi_config.get_server_info()
    host = server_info.get("host", "")
    port = server_info.get("port", 8000)
    
    if not host:
        print("No server configuration found")
        time.sleep(5)
        return
    
    # Determine ws:// or wss://
    ws_protocol = "ws"
    if str(port) == "443":
        ws_protocol = "wss"
        
    # Remove https:// or http:// from host if present
    if host.startswith("https://"):
        host = host[8:]
    elif host.startswith("http://"):
        host = host[7:]
        
    # Construct WebSocket URL
    ws_url = f"{ws_protocol}://{host}:{port}/api/ws/device/{device_mac}"
    print("Connecting to WebSocket:", ws_url)
    
    # Connect to WebSocket
    try:
        ws = uwebsockets.client.connect(ws_url)
        print("WebSocket connected")
        
        # Send initial connection message
        ws.send(json.dumps({
            "action": "connect",
            "params": {
                "device_id": device_mac,
                "version": "1.0.0"
            }
        }))
        
        # Main message loop
        while True:
            # Check for setup button press
            if check_setup_button():
                break
            
            # Wait for a message from the server with timeout
            try:
                msg = ws.recv()
                if not handle_websocket_message(ws, msg):
                    break
            except Exception as e:
                print(f"Error receiving message: {e}")
                break
    except Exception as e:
        print(f"WebSocket connection failed: {e}")
    finally:
        # Clean up
        try:
            ws.close()
        except:
            pass
        
        # Wait before reconnecting
        time.sleep(RECONNECT_DELAY)
        gc.collect()  # Run garbage collection

def main():
    """
    Main function - device initialization and main loop
    """
    global device_mac
    
    try:
        # Initialize device
        print("\n--- ESP32 Finger Bot Starting ---\n")
        
        # Load or generate device ID
        device_mac = device_id.load_device_id()
        print(f"Device MAC: {device_mac}")
        
        # Check if setup button is pressed during boot
        if not setup_button.value():  # Button is active low
            print("Setup button pressed during boot")
            enter_setup_mode()
        
        # Main loop
        while True:
            # Check for setup button press
            if check_setup_button():
                continue
            
            # Try to connect to WiFi if not connected
            if not wlan.isconnected():
                if not connect_wifi():
                    # If WiFi connection fails, enter setup mode
                    enter_setup_mode()
                    continue
            
            # Run WebSocket communication loop
            websocket_loop()
    except Exception as e:
        # Global exception handler
        sys.print_exception(e)
        print("Restarting in 10 seconds...")
        set_rgb(*LED_RED)  # Red for error
        time.sleep(10)
        machine.reset()  # Reset the device

if __name__ == "__main__":
    main()
