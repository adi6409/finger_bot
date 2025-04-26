from machine import Pin, I2C, PWM  # type: ignore
import socket
import ujson as json
import struct
import time
import network # type: ignore
# from neopixel_rgb_utils import set_rgb
# from rgb_utils import separate_rgb
from single_rgb_utils import set_rgb, blink_rgb_led
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

NETWORK_SSID = "TP-Link_Extender"
NETWORK_PASSWORD = "sNuDV9UJ"

# --- Wi-Fi Connection ---
def connect_wifi(ssid, password):
    # If wifi is already connected, return
    if wlan.isconnected():
        print("Already connected to Wi-Fi")
        return
    else:
        print("Not connected to Wi-Fi, attempting to connect...")
    # Print available networks
    print("Available networks:")
    networks = wlan.scan()
    for network in networks:
        print(network[0].decode('utf-8'), network[1], network[2], network[3])
    wlan.connect(ssid, password)

    while not wlan.isconnected():
        # set_rgb(0, 0, 255)  # Blue for connection attempt
        print("Connecting to Wi-Fi...")
        blink_rgb_led(0, 0, 255, 0.5)  # Blink blue
        time.sleep(1)
        # set_rgb(0, 0, 0)  # Off when connected
        # time.sleep(1)

    set_rgb(0, 0, 255)  # Blue for connected


    print("Connected to Wi-Fi:", wlan.ifconfig())
connect_wifi(NETWORK_SSID, NETWORK_PASSWORD)





# def toggle_on():
#     # set_rgb(0, 255, 0)
#     pass

# def toggle_off():
#     # set_rgb(255, 0, 0)
#     pass


# def press():
#     print("OOOooooo Look at meeeeeee i'm being pressed!")
#     time.sleep(1)
#     return True

# ---- Servo setup ----
SERVO_PIN = 2  # Change this to your actual GPIO pin
servo = PWM(Pin(SERVO_PIN), freq=50)  # Standard servo PWM frequency (50Hz)


def set_servo_angle(pwm, angle):
    """Set angle for SG90 servo: 0 to 180 degrees"""
    min_us = 500
    max_us = 2400
    us = int(min_us + (angle / 180) * (max_us - min_us))
    duty = int(us * 1024 * 50 / 1000000)  # duty for ESP8266 (0-1023 range)
    pwm.duty(duty)


def press():
    print("OOOooooo Look at meeeeeee i'm being pressed!")
    set_rgb(0, 255, 0)  # Green for pressed
    set_servo_angle(servo, 90)  # Rotate to 90 degrees
    time.sleep(0.5)
    set_servo_angle(servo, 0)   # Return to 0 degrees
    time.sleep(0.5)
    set_rgb(0, 0, 0)  # Off after pressing
    return True

def send_message(sock, msg):
    """Sends json message in socket"""
    msg_bytes = msg.encode()
    length = struct.pack(">H", len(msg_bytes))
    sock.send(length + msg_bytes)



def recv_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise OSError("Socket closed")
        data += chunk
    return data

def identify(s:socket.socket, dev_id):
    msg = json.dumps({"device_id": dev_id})
    print(msg)
    send_message(s, msg)
    print("Sent device id! identified!")
    



def main():
    HOST = "192.168.101.33"
    PORT = 12345
    DEVICE_ID = "ea9a27dc-f489-4dd8-bf55-626e5b83a52e"

    while True:
        try:
            s = socket.socket()
            s.connect((HOST, PORT))
            print("Connected to server")
            identify(s, DEVICE_ID)
            while True:
                # Read 2 bytes for length
                len_bytes = recv_exact(s, 2)
                msg_len = struct.unpack(">H", len_bytes)[0]
                # Read the JSON message
                msg_bytes = recv_exact(s, msg_len)
                msg_str = msg_bytes.decode()
                try:
                    msg = json.loads(msg_str)
                    action = msg.get("action")
                    params = msg.get("params")
                    print("action received: " + action)
                    # if action == "toggle_on":
                    #     toggle_on()
                    # elif action == "toggle_off":
                    #     toggle_off()

                    if action == "press":
                        print(params)
                        reqid = params.get("req_id")
                        if "scheduled" in params:
                            if params.get("scheduled") == True:
                                print("This action was scheduled!")
                        result = press()
                        response = json.dumps({"action": "press_result", "params": {"req_id": reqid, "result": result}})
                        send_message(s, response)


                except Exception as e:
                    print("Error parsing message:", e)
        except Exception as e:
            print("Socket error:", e)
            time.sleep(5)  # Wait before retrying
        finally:
            try:
                s.close()
            except:
                pass

if __name__ == "__main__":
    main()


