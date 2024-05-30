import sensor, image, time
import uasyncio as asyncio

# Initialize the sensor
sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)  # Set pixel format to Grayscale 8bit
sensor.set_framesize(sensor.QVGA)       # Set frame size to QVGA (320x240)
sensor.skip_frames(5)                   # Wait for settings to take effect

# Enable auto settings initially
sensor.set_auto_gain(True)
sensor.skip_frames(5)                   # Allow auto settings to stabilize

# Initialize buffers for smoothing over 10 frames
gain_buffer = []

history_size = 20

# Function to update buffer and maintain size of history_size values
def update_buffer(buff, value, size=history_size):
    buff.append(value)
    if len(buff) > size:
        buff.pop(0)
    return buff

# Function to calculate the weighted average of buffer values
def weighted_average(buff):
    total = sum(range(1, len(buff) + 1))
    # Weight of the value is the index
    # The most recent values are at the end
    weighted_sum = sum(value * weight for value, weight in zip(buff, range(1, len(buff) + 1)))
    return weighted_sum / total

runs = 0
update_gap = 30

async def capture_and_adjust_gain():
    global gain_buffer, runs
    while True:
        if runs % update_gap == 0:  # Update settings once every update_gap "good" frames

            # Re-enable auto settings for the next iteration
            sensor.set_auto_gain(True)
            sensor.skip_frames(5)  # Adjust this delay
            print("- - - - - -")

            # Get current auto-adjusted settings
            current_gain = sensor.get_gain_db()

            # Update buffers
            gain_buffer = update_buffer(gain_buffer, current_gain)

            # Calculate average values
            smoothed_gain = weighted_average(gain_buffer)

            # Apply the smoothed settings manually
            sensor.set_auto_gain(False, gain_db=round(smoothed_gain))
            sensor.skip_frames(5)
            print("Gain: %d" % smoothed_gain)
            runs = 1  # reset count
        else:
            # Capture image with smoothed settings
            img = sensor.snapshot()

            # display text or other overlays on the image in buffer
            #img.draw_string(10, 10, "Gain: %d" % smoothed_gain)
            runs += 1

        #print(runs)
        await asyncio.sleep(0)

async def perform_computations():
    while True:
        # CV tasks here
        print("calcs...")
        await asyncio.sleep(.1) # note -- remove delay once actual calcs are added

# Main function to run coroutines
async def main():
    task1 = asyncio.create_task(capture_and_adjust_gain())
    task2 = asyncio.create_task(perform_computations())
    await asyncio.gather(task1, task2)

# Run the main function
asyncio.run(main())
