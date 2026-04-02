from machine import I2S, Pin
import time
import machine
import sdcard
import os
import ustruct
import network
import espnow

# -----------------------
# --- EXTERNAL ANTENNA --
# -----------------------
wifi_en = Pin(3, Pin.OUT)
ant_cfg = Pin(14, Pin.OUT)
wifi_en.value(0)
time.sleep_ms(100)
ant_cfg.value(1)  # External antenna

# -----------------------
# --- SD CARD SETUP -----
# -----------------------
spi = machine.SPI(
    1,
    baudrate=4_000_000,
    polarity=0,
    phase=0,
    sck=Pin(19),
    mosi=Pin(18),
    miso=Pin(20)
)
cs = Pin(0, Pin.OUT)
sd = sdcard.SDCard(spi, cs)
vfs = os.VfsFat(sd)
os.mount(vfs, "/sd")
print("SD card mounted. Files:", os.listdir("/sd"))

# -----------------------
# --- I2S SETUP --------
# -----------------------
i2s = None

def setup_i2s(sample_rate, bit_depth):
    global i2s
    if i2s is not None:
        i2s.deinit()
    i2s = I2S(
        0,
        sck=Pin(21),
        ws=Pin(2),
        sd=Pin(1),
        mode=I2S.TX,
        bits=bit_depth,
        format=I2S.MONO,
        rate=sample_rate,
        ibuf=8192
    )
    return i2s

# -----------------------
# --- WAV PARSER -------
# -----------------------
def parse_wav_header(file):
    file.seek(0)
    header = file.read(44)
    sample_rate = ustruct.unpack('<I', header[24:28])[0]
    bit_depth = ustruct.unpack('<H', header[34:36])[0]
    num_channels = ustruct.unpack('<H', header[22:24])[0]
    print(f"  Channels: {num_channels}, Rate: {sample_rate}, Bits: {bit_depth}")
    return sample_rate, bit_depth

# -----------------------
# --- FIND SONG --------
# -----------------------
def find_song():
    """Find first songN.wav file on SD card."""
    for f in sorted(os.listdir("/sd")):
        if f.startswith("song") and f.endswith(".wav"):
            print(f"Found: {f}")
            return f
    return None

# -----------------------
# --- ESP-NOW SETUP -----
# -----------------------
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
e = espnow.ESPNow()
e.active(True)

peer = b'\xff\xff\xff\xff\xff\xff'
e.add_peer(peer)

# -----------------------
# --- STARTUP TONE ------
# -----------------------
def play_startup_tone(sample_rate):
    """Play a soft 'ding ding' through I2S to indicate speaker is on."""
    import math

    def _sine_buf(freq, duration_ms, vol=2000):
        n_samples = (sample_rate * duration_ms) // 1000
        buf = bytearray(n_samples * 2)
        for i in range(n_samples):
            # Sine wave with fade-in/fade-out envelope
            t = i / n_samples
            envelope = math.sin(t * math.pi)  # smooth rise and fall
            val = int(vol * envelope * math.sin(2 * math.pi * freq * i / sample_rate))
            ustruct.pack_into('<h', buf, i * 2, val)
        return buf

    silence = bytearray(256)
    tone1 = _sine_buf(784, 140)    # G5 — ding
    gap = bytearray(100)
    tone2 = _sine_buf(1047, 160)   # C6 — ding (higher, ascending)

    i2s.write(tone1)
    i2s.write(gap)
    i2s.write(tone2)
    i2s.write(silence)


playing = False  # start paused — wait for FD_GO

# -----------------------
# --- PLAY LOOP ---------
# -----------------------
def play_loop():
    global playing

    filename = find_song()
    if filename is None:
        print("ERROR: No songN.wav file found on SD card!")
        return

    print(f"\n--- Loading: {filename} ---")
    wav_file = open("/sd/" + filename, "rb")
    sample_rate, bit_depth = parse_wav_header(wav_file)
    setup_i2s(sample_rate, bit_depth)
    wav_file.seek(44)
    print(f"Loaded: {filename} | {sample_rate}Hz {bit_depth}-bit Mono")
    print("Paused — waiting for FD_GO to start playing")
    play_startup_tone(sample_rate)

    buffer = bytearray(1024)
    silence = bytearray(512)

    try:
        while True:
            # --- Drain all pending ESP-NOW messages ---
            try:
                while True:
                    host, msg = e.recv(0)
                    if msg is None:
                        break
                    cmd = msg.decode().strip()
                    if cmd == "FD_FREEZE" or cmd == "stop":
                        playing = False
                        i2s.write(silence)
                        print("Paused")
                    elif cmd == "FD_GO":
                        playing = True
                        print("Playing")
            except Exception as ex:
                print("ESP-NOW error:", ex)

            # --- Pause ---
            if not playing:
                time.sleep_ms(50)
                continue

            # --- Read and write audio ---
            n = wav_file.readinto(buffer)
            if n == 0:
                wav_file.seek(44)
                print("Looping...")
                continue

            i2s.write(buffer[:n])

    finally:
        wav_file.close()

# -----------------------
# --- MAIN -------------
# -----------------------
try:
    play_loop()
except KeyboardInterrupt:
    print("Interrupted by user")
except Exception as ex:
    print("Error:", ex)
finally:
    try:
        os.umount("/sd")
    except:
        pass
    print("SD card unmounted")