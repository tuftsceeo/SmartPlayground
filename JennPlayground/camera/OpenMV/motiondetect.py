# This used operations based on the OpenMV provided: Advanced Frame Differencing Example
# "This example demonstrates using frame differencing with your OpenMV Cam. This
# example is advanced because it performs a background update to deal with the
# background image changing overtime."

# Combined with smoothed lighting gain adjustments


import sensor, image, time
import uasyncio as asyncio
from machine import LED
import math

led = LED("LED_BLUE")


# Initialize the sensor
sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)  # Set pixel format to Grayscale 8bit
    #sensor.GRAYSCALE: 8-bits per pixel.
    #sensor.RGB565: 16-bits per pixel
sensor.set_framesize(sensor.QVGA)       # Set frame size to QVGA (320x240)
sensor.skip_frames(5)                   # Wait for settings to take effect

# Enable auto settings initially
sensor.set_auto_gain(True)
sensor.skip_frames(5)                   # Allow auto settings to stabilize
img = sensor.snapshot()


clock = time.clock()  # Tracks FPS

# Initialize buffers for smoothing over 10 frames
gain_buffer = []

history_size = 20

background_frames = 50



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



# Initialize gain auto smoothing updating
runs = 0 # 0 runs is updating the exposure etc
         # 1 run is the new "baseline"/control
         # perform calculations on runs >= 2
update_gap = 30



# Initialize flash memory for holding the background image
extra_bg = sensor.alloc_extra_fb(sensor.width(), sensor.height(), sensor.GRAYSCALE) #background

print("About to save background image...")
sensor.skip_frames(time=1000)
img = sensor.snapshot() # Get the first background
img.gaussian(1)
extra_bg.replace(img)
BG_UPDATE_BLEND = 254  # How much to blend background by...
                       # ([0-256]==[0%-100% new image vs prior]).

# Initialize motion detector
motion_triggered = False
mask_threshold= 25
TRIGGER_THRESHOLD = 20

start = time.ticks_ms()
BG_RESET = 1000 #number of milliseconds to wait before allowing a background
                        # update despite triggered state

force_new_bg = False
new_frame = False


async def capture_and_adjust_gain():
    global gain_buffer, runs, new_frame, img, extra_bg, force_new_bg
    while True:
        if runs % update_gap == 0:  # Update settings once every update_gap "good" frames

            # Re-enable auto settings for the next iteration
            sensor.set_auto_gain(True)
            sensor.skip_frames(5)  # Adjust this delay


            # Get current auto-adjusted settings
            current_gain = sensor.get_gain_db()

            # Update buffers
            gain_buffer = update_buffer(gain_buffer, current_gain)

            # Calculate average values
            smoothed_gain = weighted_average(gain_buffer)

            # Apply the smoothed settings manually
            sensor.set_auto_gain(False, gain_db=smoothed_gain)
            sensor.skip_frames(5)
            print("Gain: %2.2f" % smoothed_gain)
            runs = 1  # reset count
        else:
            # Capture image with smoothed settings
            img = sensor.snapshot()
            img.gaussian(1)
            new_frame = True

            # Optionally display text or other overlays on the image
            #img.draw_string(10, 10, "Gain: %d" % smoothed_gain)

            if runs % 5 == 0:
                # use every fifth frame to update for motion detection
                extra_bg.replace(sensor.snapshot().gaussian(1))


            runs += 1

        #print(runs)
        await asyncio.sleep(0)


def find_nearest_blob(blob, previous_blobs):
    # Use nearest neighbor to find previous blob
    nearest_blob = None
    nearest_distance = float('inf')
    nearest_blob_id = None
    for key in previous_blobs:
        prev_blob = previous_blobs[key][0]
        distance = math.sqrt((blob.cx() - prev_blob.cx())**2 + (blob.cy() - prev_blob.cy())**2)
        if distance < nearest_distance:
            nearest_distance = distance
            nearest_blob = prev_blob
            nearest_blob_id = key
    if nearest_blob:
        good_distance = (nearest_distance < sensor.width() / 10)
        good_area = nearest_blob.area()*.50<blob.area() and blob.area()<nearest_blob.area()*2
        print("Blob distance ", nearest_distance, " area is ", good_area)
        if good_distance and good_area:
            print("Blob ID", nearest_blob_id)
            return nearest_blob_id, nearest_blob, nearest_distance

    return None, None, None

async def perform_computations():
    global new_frame, motion_triggered, force_new_bg, bad_blob_counter
    frame_count=0
    previous_blobs = {}
    bad_blob_counter = 0
    while True:
        if new_frame:
            frame_count += 1

            new_frame = False
            clock.tick()

            # Replace the image with the "abs(NEW-OLD)" frame difference.
            img.difference(extra_bg)
            img.binary([(mask_threshold,255)])
            img.dilate(1)

            blobs = img.find_blobs([(mask_threshold,255)], pixels_threshold=50, area_threshold=50, merge=True)
            i = 0
            print(' - - - ')
            for blob in blobs:

                print("B", blob.area(), blob.cx(), blob.cy())
                i += 1

                img.draw_rectangle(blob.rect(), color=127)
                img.draw_cross(blob.cx(), blob.cy(), color=127)
                # Note - the blob rotation is unique to 0-180 only.

                nearest_blob_id, nearest_blob, nearest_distance = find_nearest_blob(blob, previous_blobs)

                if not nearest_blob:
                    # add new object - blob, time last seen, time last movement
                    if len(previous_blobs) == 0:
                        previous_blobs[0] = [blob, time.ticks_ms(), time.ticks_ms()]
                    else:
                        previous_blobs[max(previous_blobs.keys())+1] = [blob, time.ticks_ms(), time.ticks_ms()]
                    print("ADD NEW BLOB ID:", max(previous_blobs.keys()))
                elif nearest_distance > sensor.width() / 30:
                    # update last movement
                    time_since_update = time.ticks_diff(time.ticks_ms(),previous_blobs[nearest_blob_id][2])
                    #speed = nearest_distance/time_since_update
                    previous_blobs[nearest_blob_id][0] = blob
                    previous_blobs[nearest_blob_id][1] = time.ticks_ms()
                    previous_blobs[nearest_blob_id][2] = time.ticks_ms()  # update last movement time
                    print("Blob ", nearest_blob_id, " has MOVED ", nearest_distance, "in", time_since_update)
                elif time.ticks_diff(time.ticks_ms(),previous_blobs[nearest_blob_id][2]) > 5000:
                    #check if it hasn't moved in the last 5 seconds, start to flag
                    bad_blob_counter +=1
                    previous_blobs[nearest_blob_id][1] = time.ticks_ms() # update last seen
                    print("Blob ", nearest_blob_id, " has not moved")
                else:
                    previous_blobs[nearest_blob_id][1] = time.ticks_ms() # update last seen
                    print("Blob ", nearest_blob_id, " has not moved")




                #if the bounding rectangle fills most of the screen
                if blob.area() > .6 * sensor.width()*sensor.height():
                    print("Blocked Screen, big blob")
                    bad_blob_counter += 5

            #Remove blobs that have not been seen in a while
            for key in previous_blobs:
                prev_blob = previous_blobs[key]
                # If you've not seen that blog in 5 seconds assume it is gone
                if time.ticks_diff(time.ticks_ms(),prev_blob[1]) > 5000:
                    print("Blob ", key, " lost sight")
                    del previous_blobs[key]
            #print(bad_blob_counter)

            if bad_blob_counter > 200:
                # If the counter gets high, reset background entirely.
                # Assume camera motion or lighting shift
                force_new_bg = True
                prior_blobs = {} # reset blob tracking
                bad_blob_counter = 0

            white_pixels = sum(blob.pixels() for blob in blobs)
            print("END", clock.fps(), white_pixels, bad_blob_counter, len(previous_blobs) )



            motion_triggered = white_pixels > TRIGGER_THRESHOLD
            if motion_triggered:
                led.on()
            else:
                led.off()
            #print(clock.fps(), motion_triggered, diff)

        await asyncio.sleep(0)

# Main function to run coroutines
async def main():
    task1 = asyncio.create_task(capture_and_adjust_gain())
    task2 = asyncio.create_task(perform_computations())
    await asyncio.gather(task1, task2)

# Run the main function
asyncio.run(main())





#if blob.elongation() > 0.5:
#                    rot = int(math.degrees(blob.rotation()))
#                    img.draw_keypoints(
#                        [(blob.cx(), blob.cy(), rot)],
#                        size=40,
#                        color=127,
#                    )
#                    # ARE there blobs that are not moving?
#                    if not rot in prior_blobs:
#                        # add new directional object - location, time first seen, time last seen
#                        prior_blobs[rot] = [blob.cx(), blob.cy(), time.ticks_ms(), time.ticks_ms()]
#                    else :
#                        # if it's there - check location
#                        if abs(prior_blobs[rot][0] - blob.cx())>sensor.width()/12 or \
#                                abs(prior_blobs[rot][1] - blob.cy())>sensor.height()/12:
#                                    #if it's moved update location and times
#                                prior_blobs[rot] = [blob.cx(), blob.cy(), time.ticks_ms(), time.ticks_ms()]
#                        else:
#                            #only update last seen time
#                                prior_blobs[rot][3] = time.ticks_ms()
#                        if time.ticks_diff(time.ticks_ms(),prior_blobs[rot][2]) > 5000:
#                            #check if it hasn't moved in the last 5 seconds, start to flag
#                            bad_blob_counter +=1


