from machine import Pin, SoftI2C, PWM, ADC
import time
import machine
import prefs
from files import *
import ssd1306

# === Track time since boot ===
boot_start = time.ticks_ms()

# === Input Pins ===
switch_down = Pin(8, Pin.IN, Pin.PULL_UP)
switch_select = Pin(9, Pin.IN, Pin.PULL_UP)
switch_up = Pin(10, Pin.IN, Pin.PULL_UP)

# === OLED and I2C Setup ===
i2c = SoftI2C(scl=Pin(7), sda=Pin(6))
screen = ssd1306.SSD1306_I2C(128, 64, i2c)

# === Potentiometer for horizontal scroll ===
pot = ADC(Pin(3))
pot.atten(ADC.ATTN_11DB)

# === Menu Items and UI State ===
menu_items = ["Standalone", "Web Connect", "Linear Regression", "Exit"]
selected_index = 0
scroll_index = 0
max_visible_items = 2
row_height = 24
line_width_chars = 21
scroll_offset_chars = 0  # updated by pot

# === UI Helpers ===
def flash_message(msg, duration=0.3):
    screen.fill(0)
    screen.text(msg, 10, 25, 1)
    screen.show()
    time.sleep(duration)

def log_trigger(ms):
    try:
        with open("trigger_log.txt", "a") as f:
            f.write("Triggered at {} ms\n".format(ms))
    except:
        flash_message("Log failed", 1)

# === Scroll Update from Potentiometer ===
def update_scroll():
    global scroll_offset_chars
    label = menu_items[selected_index]
    max_offset = max(len(label) - line_width_chars, 0)

    if max_offset == 0:
        scroll_offset_chars = 0
        return

    pot_value = pot.read()
    normalized = pot_value / 4095
    scroll_offset_chars = int(normalized * max_offset)
    scroll_offset_chars = min(scroll_offset_chars, max_offset)

# === Display Menu with Pot Scrolling ===
def display_menu():
    screen.fill(0)
    screen.text("Choose Mode", 25, 0, 1)
    screen.hline(0, 10, 128, 1)

    for i in range(max_visible_items):
        idx = scroll_index + i
        if idx >= len(menu_items):
            break

        y = 12 + i * row_height
        label = str(menu_items[idx])

        if idx == selected_index:
            screen.fill_rect(0, y, 128, row_height, 1)

            scroll_safe = min(scroll_offset_chars, max(len(label) - line_width_chars, 0))
            padded = label + " " * (line_width_chars + 1)
            visible = padded[scroll_safe:scroll_safe + line_width_chars]
            screen.text("> " + visible, 2, y, 0)

        else:
            visible = label[:line_width_chars]
            if len(visible) < line_width_chars:
                visible += " " * (line_width_chars - len(visible))
            screen.text("  " + visible, 2, y, 1)

    screen.show()

# === Move selection up/down ===
def move_selection(direction):
    global selected_index, scroll_index, scroll_offset_chars
    new_index = selected_index + direction
    if 0 <= new_index < len(menu_items):
        selected_index = new_index
        scroll_offset_chars = 0  # Reset scroll when selection changes
        if selected_index >= scroll_index + max_visible_items:
            scroll_index = selected_index - max_visible_items + 1
        elif selected_index < scroll_index:
            scroll_index = selected_index

# === SET MODE ===
def setmode():
    try:
        mode = prefs.get_mode()
    except:
        mode = 0

    time.sleep(0.1)
    up = switch_up.value()
    down = switch_down.value()
    select = switch_select.value()

    if up == 0 or down == 0 or select == 0:
        timestamp = time.ticks_diff(time.ticks_ms(), boot_start)
        log_trigger(timestamp)

        screen.fill(0)
        screen.text("Trig: {}ms".format(timestamp), 20, 28, 1)
        screen.show()
        time.sleep(0.8)

        while True:
            if switch_up.value() == 0 and switch_down.value() == 0:
                time.sleep(0.05)
                if switch_up.value() == 0 and switch_down.value() == 0:
                    flash_message("Both Buttons!")
                    while switch_up.value() == 0 or switch_down.value() == 0:
                        time.sleep(0.1)

            elif switch_up.value() == 0:
                while switch_up.value() == 0:
                    time.sleep(0.1)
                move_selection(1)

            elif switch_down.value() == 0:
                while switch_down.value() == 0:
                    time.sleep(0.1)
                move_selection(-1)

            if switch_select.value() == 0:
                while switch_select.value() == 0:
                    time.sleep(0.1)

                selection = str(menu_items[selected_index])
                if selection == "Standalone":
                    prefs.resetprefs(0)
                    flash_message("Standalone Selected", 1)
                    return 0
                elif selection == "Web Connect":
                    prefs.resetprefs(1)
                    flash_message("Web Connect Selected", 1)
                    return 1
                elif selection == "Linear Regression":
                    prefs.resetprefs(2)
                    flash_message("Regression Mode", 1)
                    return 2
                elif selection == "Exit":
                    flash_message("Keeping Mode", 1)
                    return mode

            update_scroll()       # <-- live scroll from pot
            display_menu()
            time.sleep(0.05)

    return mode

# === Main Function ===
def main():
    flash_message("Welcome!", 1.5)
    mode = setmode()

    if mode == 0:
        flash_message("Running Standalone", 1.5)
        # Add standalone logic here
    elif mode == 1:
        flash_message("Connecting to Web...", 1.5)
        # Add web connect logic here
    elif mode == 2:
        flash_message("Running Regression", 1.5)
        # Add linear regression logic here

# === Run on Boot ===
if __name__ == "__main__":
    main()