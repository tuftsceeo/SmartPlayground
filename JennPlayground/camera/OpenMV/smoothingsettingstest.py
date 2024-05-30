import sensor, image, time

# Initialize the sensor
sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)  # Set pixel format to Grayscale 8bit
                    #sensor.GRAYSCALE: 8-bits per pixel.
                    #sensor.RGB565: 16-bits per pixel.
sensor.set_framesize(sensor.QVGA)     # Set frame size to QVGA (320x240)
                    # sensor.QQVGA: 160x120
                    # sensor.QVGA: 320x240
                    # sensor.VGA: 640x480
sensor.skip_frames(5)        # Wait for settings to take effect

# Enable auto settings initially
sensor.set_auto_exposure(True)
sensor.set_auto_gain(True)
sensor.set_auto_whitebal(True)
sensor.skip_frames(5)         # Allow auto settings to stabilize

# Initialize buffers for smoothing over 10 frames
exposure_buffer = []
gain_buffer = []
whitebal_buffer = []

history_size = 20

# Function to update buffer and maintain size of history_size values
def update_buffer(buff, value, size=history_size):
    buff.append(value)
    if len(buff) > size:
        buff.pop(0)
    return buff

# Function to calculate the average of buffer values
def weighted_average(buff):
    total = sum(range(1, len(buff) + 1))
    # Weight of the value is the index
    # The most recent values are at the end
    weighted_sum = sum(value * weight for value, weight in zip(buff, range(1, len(buff) + 1)))
    return weighted_sum / total

runs = 0
update_gap = 30

while(True):
    if runs % update_gap == 0: # Update settings once every update_gap "good" frames

        # Re-enable auto settings for the next iteration
        sensor.set_auto_exposure(True)
        sensor.set_auto_gain(True)
        sensor.set_auto_whitebal(True)
        sensor.skip_frames(5)  # Adjust this delay
        print("- - - - - -")
        # Capture image with auto settings to get current values
        #img = sensor.snapshot()

        # Get current auto-adjusted settings
        current_exposure = sensor.get_exposure_us()
        current_gain = sensor.get_gain_db()
        current_whitebal = sensor.get_rgb_gain_db()

        # Update buffers
        exposure_buffer = update_buffer(exposure_buffer, current_exposure)
        gain_buffer = update_buffer(gain_buffer, current_gain)
        whitebal_buffer = update_buffer(whitebal_buffer, current_whitebal)

        # Calculate average values
        smoothed_exposure = weighted_average(exposure_buffer)
        smoothed_gain = weighted_average(gain_buffer)
        smoothed_whitebal = (
            weighted_average([wb[0] for wb in whitebal_buffer]),
            weighted_average([wb[1] for wb in whitebal_buffer]),
            weighted_average([wb[2] for wb in whitebal_buffer])
        )

        # Apply the smoothed settings manually
        sensor.set_auto_whitebal(False,  rgb_gain_db=(smoothed_whitebal))
        sensor.set_auto_exposure(False, exposure_us=round(smoothed_exposure))
        sensor.set_auto_gain(False, gain_db=round(smoothed_gain))
        sensor.skip_frames(5)
        print("Exposure: %d" % smoothed_exposure)
        print("Gain: %d" % smoothed_gain)
        print("WhiteBal: R:%d G:%d B:%d" % smoothed_whitebal)
        runs = 1 # reset count
    else:
        # Capture image with smoothed settings
        img = sensor.snapshot()

        # Optionally display text or other overlays on the image
        img.draw_string(10, 10, "Exposure: %d" % smoothed_exposure)
        img.draw_string(10, 30, "Gain: %d" % smoothed_gain)
        img.draw_string(10, 50, "WhiteBal: R:%d G:%d B:%d" % smoothed_whitebal)
        runs = runs + 1
    #print(runs)

