from machine import I2S, Pin
import time
import machine
import sdcard
import os
import ustruct
import network
import espnow

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
# --- SONG LIST --------
# -----------------------
LAST_SONG_FILE = "/sd/lastsong.txt"

def find_songs():
    """Find all songN.wav files on SD and return sorted list."""
    songs = []
    for f in os.listdir("/sd"):
        if f.startswith("song") and f.endswith(".wav"):
            songs.append(f)
    songs.sort()
    print(f"Found {len(songs)} songs: {songs}")
    return songs

def load_last_song(songs):
    """Read last played song index from file. Returns 0 if not found."""
    try:
        with open(LAST_SONG_FILE, "r") as f:
            name = f.read().strip()
            if name in songs:
                idx = songs.index(name)
                print(f"Resuming: {name} (index {idx})")
                return idx
    except:
        pass
    print("No saved song found, starting at song 0")
    return 0

def save_last_song(name):
    """Save current song name to file."""
    try:
        with open(LAST_SONG_FILE, "w") as f:
            f.write(name)
    except Exception as ex:
        print("Could not save last song:", ex)

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
# --- VOLUME CONTROL ----
# -----------------------
VOL_LEVELS = [0, 10, 25, 40, 55, 70, 85, 100]
vol_index = 7  # start at 100%

def apply_volume(buf, n):
    """Scale 16-bit samples in-place using integer math."""
    vol = VOL_LEVELS[vol_index]
    if vol == 100:
        return
    for i in range(0, n, 2):
        sample = ustruct.unpack_from('<h', buf, i)[0]
        sample = (sample * vol) // 100
        ustruct.pack_into('<h', buf, i, sample)

# -----------------------
# --- GLOBAL STATE ------
# -----------------------
playing = True
song_changed = False
current_index = 0

# -----------------------
# --- PLAY LOOP ---------
# -----------------------
def play_loop():
    global playing, song_changed, current_index

    songs = find_songs()
    if len(songs) == 0:
        print("ERROR: No songN.wav files found on SD card!")
        return

    current_index = load_last_song(songs)
    song_changed = True  # trigger first song load

    buffer = bytearray(4096)
    silence = bytearray(512)
    wav_file = None
    loop_count = 0

    try:
        while True:
            # --- Load new song if changed ---
            if song_changed:
                song_changed = False
                if wav_file:
                    wav_file.close()

                filename = songs[current_index]
                print(f"\n--- Loading: {filename} ({current_index + 1}/{len(songs)}) ---")
                save_last_song(filename)

                wav_file = open("/sd/" + filename, "rb")
                sample_rate, bit_depth = parse_wav_header(wav_file)
                setup_i2s(sample_rate, bit_depth)
                wav_file.seek(44)
                playing = True
                print(f"Playing: {filename} | {sample_rate}Hz {bit_depth}-bit Mono")

            # --- Check ESP-NOW every ~20 iterations ---
            loop_count += 1
            if loop_count % 20 == 0:
                try:
                    host, msg = e.recv(0)
                    if msg:
                        cmd = msg.decode().strip()
                        if cmd == "FD_FREEZE":
                            playing = False
                            i2s.write(silence)
                            print("Paused")
                        elif cmd == "FD_GO":
                            playing = True
                            print("Playing")
                        elif cmd == "FD_NEXT":
                            current_index = (current_index + 1) % len(songs)
                            song_changed = True
                            print(">> Next")
                            continue
                        elif cmd == "FD_PREV":
                            current_index = (current_index - 1) % len(songs)
                            song_changed = True
                            print("<< Previous")
                            continue
                        elif cmd == "FD_VOL_UP":
                            vol_index = min(vol_index + 1, len(VOL_LEVELS) - 1)
                            print(f"Volume: {VOL_LEVELS[vol_index]}%")
                        elif cmd == "FD_VOL_DOWN":
                            vol_index = max(vol_index - 1, 0)
                            print(f"Volume: {VOL_LEVELS[vol_index]}%")
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

            # --- Apply volume and write ---
            apply_volume(buffer, n)
            i2s.write(buffer[:n])

    finally:
        if wav_file:
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