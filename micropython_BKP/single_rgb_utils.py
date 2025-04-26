from machine import Pin, I2C # type: ignore
import time
RED_PIN = 17
GREEN_PIN = 19
BLUE_PIN = 20

red = Pin(RED_PIN, Pin.OUT)
green = Pin(GREEN_PIN, Pin.OUT)
blue = Pin(BLUE_PIN, Pin.OUT)

# --- RGB Functions ---
def set_rgb(r, g, b):
    red.value(r)
    green.value(g)
    blue.value(b)

def blink_rgb_led(r, g, b, duration=0.5):
    set_rgb(r, g, b)
    time.sleep(duration)
    set_rgb(0, 0, 0)  # Turn off the LED
    time.sleep(duration)