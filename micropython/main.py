"""
Main module for the ESP32 Finger Bot device.
This module handles the device setup, WiFi connection, and server communication.
"""

from machine import Pin, PWM  # type: ignore
import ujson as json
import time
import network  # type: ignore
import machine  # type: ignore
import gc

# Import custom modules
from single_rgb_utils import set_rgb, blink_rgb_led
import device_id
import wifi_config
import ble_setup

# --- Constants ---
SETUP_BUTTON_PIN = 0  # GPIO0 is often the BOOT button on ESP32 boards
SERVO_PIN = 2  # GPIO2 for servo control
SETUP_MODE_TIMEOUT = 300  # 5 minutes timeout for setup mode

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
    """Set angle for SG90 servo: 0 to 180 degrees"""
    min_us = 500
    max_us = 2400
    us = int(min_us + (angle / 180) * (max_us - min_us))
    duty = int(us * 1024 * 50 / 1000000)  # duty for ESP8266 (0-1023 range)
    pwm.duty(duty)

def press():
    """Perform the press action with the servo"""
    print("Performing press action")
    set_rgb(0, 255, 0)  # Green for pressed
    set_servo_angle(servo, 90)  # Rotate to 90 degrees
    time.sleep(0.5)
    set_servo_angle(servo, 0)   # Return to 0 degrees
    time.sleep(0.5)
    set_rgb(0, 0, 0)  # Off after pressing
    return True

def connect_wifi():
    """Connect to WiFi using stored credentials"""
    if wlan.isconnected():
        print("Already connected to WiFi")
        return True
    
    config = wifi_config.load_config()
    ssid = config.get("ssid", "")
    password = config.get("password", "")
    
    if not ssid:
        print("No WiFi configuration found")
        return False
    
    print(f"Connecting to WiFi: {ssid}")
    wlan.connect(ssid, password)
    
    # Wait for connection with timeout
    max_wait = 20
    while max_wait > 0:
        if wlan.isconnected():
            print("Connected to WiFi:", wlan.ifconfig())
            set_rgb(0, 0, 255)  # Blue for connected
            return True
        max_wait -= 1
        print("Connecting to WiFi...")
        blink_rgb_led(0, 0, 255, 0.5)  # Blink blue
        time.sleep(1)
    
    print("Failed to connect to WiFi")
    return False

def enter_setup_mode():
    """Enter device setup mode with BLE advertising"""
    global setup_mode, ble
    
    print("Entering setup mode")
    setup_mode = True
    set_rgb(0, 0, 255)  # Blue for setup mode
    
    # Initialize BLE
    ble = ble_setup.BLESetup(f"ESP32-{device_mac[-6:]}")
    ble.start()
    
    # Stay in setup mode for a limited time
    setup_start_time = time.time()
    while setup_mode and (time.time() - setup_start_time < SETUP_MODE_TIMEOUT):
        # Check if setup is complete (WiFi configured)
        if ble._config.get("ssid"):
            # Save the WiFi configuration
            wifi_config.save_config(ble._config)
            print("WiFi configuration saved")
            setup_mode = False
            break
        
        # Blink LED to indicate setup mode
        blink_rgb_led(0, 0, 255, 0.5)  # Blink blue
        time.sleep(0.5)
    
    # Exit setup mode
    if ble:
        ble.stop()
        ble = None
    
    setup_mode = False
    set_rgb(0, 0, 0)  # Turn off LED
    print("Exiting setup mode")

def check_setup_button():
    """Check if the setup button is pressed"""
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

def main():
    """Main function"""
    global device_mac
    
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

        # --- WebSocket Communication ---
        try:
            import uwebsockets.client
        except ImportError:
            print("uwebsockets.client not found. Please upload uwebsockets library to the device.")
            time.sleep(10)
            continue

        server_info = wifi_config.get_server_info()
        host = server_info.get("host", "")
        port = server_info.get("port", 8000)
        if not host:
            print("No server configuration found")
            time.sleep(5)
            continue

        # Determine ws:// or wss://
        ws_protocol = "ws"
        if str(port) == "443":
            ws_protocol = "wss"
        ws_url = "{}://{}:{}/ws/device/{}".format(ws_protocol, host, port, device_mac)
        print("Connecting to WebSocket:", ws_url)

        try:
            ws = uwebsockets.client.connect(ws_url)
            print("WebSocket connected")
        except Exception as e:
            print("WebSocket connection failed:", e)
            time.sleep(5)
            continue

        try:
            while True:
                # Check for setup button press
                if check_setup_button():
                    break

                # Wait for a message from the server
                msg = ws.recv()
                if not msg:
                    print("WebSocket closed by server")
                    break

                print("Received message:", msg)
                try:
                    data = json.loads(msg)
                except Exception as e:
                    print("Invalid JSON from server:", e)
                    continue

                action = data.get("action")
                params = data.get("params", {})

                if action == "press":
                    print("Executing press action")
                    press()
                    # Optionally, send result back via HTTP or WebSocket
                    # ws.send(json.dumps({"action": "press_result", "params": {"result": True}}))

        except Exception as e:
            print("WebSocket error:", e)
        finally:
            try:
                ws.close()
            except:
                pass
            time.sleep(5)
            gc.collect()  # Run garbage collection

if __name__ == "__main__":
    main()
