from machine import Pin, I2C # type: ignore
import neopixel #type: ignore


RGB_PIN = 39

NUM_PIXELS = 1
np = neopixel.NeoPixel(Pin(RGB_PIN), NUM_PIXELS)

# --- RGB Functions ---
def set_rgb(r, g, b):
    np[0] = (r, g, b)
    np.write()
