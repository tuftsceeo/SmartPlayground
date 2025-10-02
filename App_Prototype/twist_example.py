"""
Rainbow Twist Example - 24 ticks = full color spectrum
"""
from qwiic_twist import QwiicTwist
import time

def hsv_to_rgb(hue, sat=1, val=1):
    """Convert HSV to RGB (hue 0-360)"""
    h = hue % 360
    c = val * sat
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = val - c
    
    if h < 60: r, g, b = c, x, 0
    elif h < 120: r, g, b = x, c, 0
    elif h < 180: r, g, b = 0, c, x
    elif h < 240: r, g, b = 0, x, c
    elif h < 300: r, g, b = x, 0, c
    else: r, g, b = c, 0, x
    
    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)

def count_to_rainbow(count):
    """Map encoder count to rainbow colors (24 ticks = full spectrum)"""
    hue = (count % 24) * 15  # 24 ticks * 15° = 360°
    return hsv_to_rgb(hue)

twist = QwiicTwist()

if twist.connected:
    print("Rainbow Twist ready!")
    twist.begin()
    twist.count = 0  # Reset count to zero
    
    while True:
        count = twist.count
        pressed = twist.pressed
        
        # Set rainbow color based on count
        r, g, b = count_to_rainbow(count)
        twist.set_color(r, g, b)
        
        print(f"Count: {count:2d} | Color: R{r:3d} G{g:3d} B{b:3d} | Button: {'ON' if pressed else 'OFF'}")
        
        time.sleep(0.1)
else:
    print("Not connected")