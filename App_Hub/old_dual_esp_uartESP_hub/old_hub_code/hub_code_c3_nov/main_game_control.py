from machine import Pin, SPI, Timer
import espnow
import network
import time
import ujson as json
import os
from playertracker import PlayerTracker
from gamestate import GameState
from max7219 import Max7219

# --- Pin Constants for XIAO ESP32-C3 ---
CODER_BUTTON_PIN = 0          # D0
UNDO_BUTTON_PIN = 1           # D1
PLAYER_BUTTON_PINS = [3, 4, 5, 6]  # D3, D4, D5, D6
NEOPIXEL_PIN = 7              # D7
SPI_SCK_PIN = 8               # D8 (SCK for MAX7219)
SPI_MOSI_PIN = 10             # D10 (MOSI for MAX7219)
MAX7219_CS_PIN = 2            # D2 (CS for MAX7219)

# --- Constants ---
INACTIVITY_TIMEOUT = 600  # 10 minutes in seconds
DISCONNECTION_TIMEOUT = 300  # 5 minutes in seconds
GAME_STATE_FILE = "game_state.json"
REQUEST_TIMEOUT = 5  # 5 seconds for request timeout

# --- ESP-NOW Setup ---
sta = network.WLAN(network.STA_IF)
sta.active(True)

esp_now = espnow.ESPNow()
esp_now.init()

# --- Initialize Classes ---
game_state = GameState(coder_mac=None)
player_tracker = PlayerTracker(pin=NEOPIXEL_PIN)

# --- MAX7219 Setup ---
spi = SPI(1, baudrate=10000000, sck=Pin(SPI_SCK_PIN), mosi=Pin(SPI_MOSI_PIN))
cs = Pin(MAX7219_CS_PIN, Pin.OUT)
max_display = Max7219(64, 8, spi, cs)  # 8 matrices (64 pixels wide, 8 pixels high)

# --- Button Setup ---
coder_button = Pin(CODER_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
undo_button = Pin(UNDO_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
player_buttons = [Pin(pin, Pin.IN, Pin.PULL_UP) for pin in PLAYER_BUTTON_PINS]

# --- Timer for Inactivity Tracking ---
last_activity = {}

def reset_activity(mac_address):
    """Reset the last activity time for a player."""
    last_activity[mac_address] = time.time()

def check_timeouts(timer):
    """Remove players who have timed out due to inactivity or disconnection."""
    game_state.remove_inactive_players(INACTIVITY_TIMEOUT)
    player_tracker.reset_all_progress()

# Start a timer to check for timeouts every 30 seconds
timeout_timer = Timer(0)
timeout_timer.init(period=30000, mode=Timer.PERIODIC, callback=check_timeouts)

# --- Save and Load Game State ---
def save_game_state(filename):
    """Save the current game state to a file."""
    with open(filename, "w") as f:
        json.dump(game_state.to_dict(), f)
    print("Game state saved.")

def load_game_state(filename):
    """Load the game state from a file."""
    with open(filename, "r") as f:
        data = json.load(f)
        game_state.from_dict(data)
        player_tracker.reset_all_progress()
        print("Previous game state loaded.")

def backup_and_load_previous_game():
    """Backup the current game and load the previous game state."""
    if os.path.exists(GAME_STATE_FILE):
        save_game_state("backup_" + GAME_STATE_FILE)
        load_game_state(GAME_STATE_FILE)

# --- Button Handlers ---
def add_coder_handler(pin):
    """Handler to initiate adding a coder."""
    print("Requesting coder...")
    save_game_state(GAME_STATE_FILE)
    game_state.reset_game()
    player_tracker.reset_all_progress()
    player_tracker.indicate_request(0, color=(0, 0, 255))  # Blue light for coder request
    esp_now.send(b'\xff' * 6, b'REQUEST_CODER')

def add_player_handler(pin, player_number):
    """Handler to initiate adding a specific player."""
    print(f"Requesting player {player_number}...")
    player_tracker.indicate_request(player_number, color=(0, 255, 0))  # Green light for player request
    esp_now.send(b'\xff' * 6, f'REQUEST_PLAYER_{player_number}'.encode())

def undo_handler(pin):
    """Handler to recover the previous game state."""
    print("Undoing last reset...")
    backup_and_load_previous_game()

# Assign button handlers
coder_button.irq(trigger=Pin.IRQ_FALLING, handler=add_coder_handler)
undo_button.irq(trigger=Pin.IRQ_FALLING, handler=undo_handler)
for i, button in enumerate(player_buttons):
    button.irq(trigger=Pin.IRQ_FALLING, handler=lambda pin, num=i+1: add_player_handler(pin, num))

# --- ESP-NOW Receive Handler ---
def on_receive_callback():
    while True:
        host, msg = esp_now.recv()
        if msg:
            msg = msg.decode()
            print(f"Received from {host}: {msg}")

            # Handle coder confirmation
            if msg == 'CODER_CONFIRM':
                game_state.coder_mac = host
                print(f"Coder confirmed: {host}")
                reset_activity(host)

            # Handle player confirmation
            elif msg.startswith('PLAYER_CONFIRM_'):
                player_number = int(msg.split('_')[2])
                game_state.add_player(host)
                reset_activity(host)
                print(f"Player {player_number} confirmed: {host}")

            # Handle sequence broadcast
            elif msg.startswith('SEQUENCE:') and host == game_state.coder_mac:
                sequence = list(map(int, msg.split(':')[1].split(',')))
                game_state.set_sequence(sequence)
                player_tracker.display_coder_sequence(sequence)
                max_display.draw_5x3_list(sequence)
                max_display.show()
                print(f"Sequence received: {sequence}")

            # Handle player progress update
            elif msg.startswith('STEP:'):
                step = int(msg.split(':')[1])
                if host in game_state.players:
                    game_state.update_progress(host, step)
                    player_index = list(game_state.players.keys()).index(host)
                    player_tracker.update_player_progress(player_index, step, game_state.sequence)
                    reset_activity(host)

# --- Main Loop ---
def main():
    print("Game controller initialized. Waiting for input...")
    on_receive_callback()

if __name__ == "__main__":
    main()
