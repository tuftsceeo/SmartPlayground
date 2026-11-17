# Mockup app: the seven screens with fake data. No radio, no NFC, no file transfer.
# Never run on the board. Start from main.py.
import time
import lvgl as lv
import hw_display


def run():
    keep = hw_display.init()
    import ui
    import scr_home
    import scr_games
    import scr_tags
    import scr_write
    import scr_read
    import scr_serve
    ui.go("home")
    while True:
        lv.refr_now(None)
        time.sleep_ms(30)
