import machine, neopixel
import time

NUM_LEDS = 1
np = neopixel.NeoPixel(machine.Pin(7), NUM_LEDS)

np[0] = (128, 128, 0) # set to red, full brightness
np.write()

def hue(pos):
    """
    Generate RGB color across 0-255 positions.
    
    :param pos: Position in the color wheel (0-255)
    :return: Tuple (R, G, B) - the color corresponding to the position
    """
    if pos < 85:
        return (int(255 - pos*3), int(pos * 3), 0)  # 0 is red
    elif pos < 170:
        pos -= 85
        return (0, int(255 - pos*3), int(pos * 3))  # 85 is green
    else:
        pos -= 170
        return (int(pos*3), 0, int(255 - pos * 3))  # 170 is blue


def rainbow_cycle(wait):
    """Display a rainbow cycle across the entire LED strip."""
    for j in range(256):  # Loop through 256 color positions
        print(j)
        for i in range(NUM_LEDS):  # Loop through each LED
            pixel_index = (i * 256 // NUM_LEDS) + j  # Calculate color position
            np[i] = hue(pixel_index & 255)  # Set the LED to the color
        np.write() 
        time.sleep(wait)  # Pause for a short time before the next update

rainbow_cycle(.1)
