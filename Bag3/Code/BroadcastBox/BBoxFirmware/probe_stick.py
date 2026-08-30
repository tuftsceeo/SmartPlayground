"""
probe_stick.py — Phase 0 bench checks for M5Stack StickS3 (UIFlow2).

Deploy to /flash and run:
  mpremote connect /dev/cu.usbmodem3101 fs cp probe_stick.py :/flash/probe_stick.py
  mpremote connect /dev/cu.usbmodem3101 exec "import probe_stick; probe_stick.run()"
"""

import time

RESULTS = []


def _result(key, value, ok=True):
    line = "RESULT %s=%s ok=%s" % (key, value, "1" if ok else "0")
    print(line)
    RESULTS.append((key, value, ok))


def _check_ap_socket():
    import network
    import socket
    ok = True
    ap = network.WLAN(network.AP_IF)
    try:
        ap.active(True)
        try:
            ap.config(essid='SP-PROBE', password='playground1', authmode=3)
        except (ValueError, OSError):
            ap.config(essid='SP-PROBE', password='playground1', security=3)
        while not ap.active():
            time.sleep_ms(100)
        ip = ap.ifconfig()[0]
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('0.0.0.0', 8266))
        srv.listen(1)
        srv.close()
        ap.active(False)
        _result("ap_socket", ip, True)
    except Exception as e:
        ok = False
        _result("ap_socket", str(e), False)
        try:
            ap.active(False)
        except Exception:
            pass
    return ok


def _check_lcd():
    try:
        import M5
        M5.begin()
        M5.Lcd.setRotation(1)
        font = getattr(M5.Lcd.FONTS, "DejaVu18", None)
        if font:
            M5.Lcd.setFont(font)
        M5.Lcd.fillScreen(0x111111)
        M5.Lcd.setCursor(10, 60)
        M5.Lcd.setTextColor(0xFFFFFF, 0x111111)
        M5.Lcd.print("Probe OK 240px")
        _result("lcd", "DejaVu18", True)
        return True
    except Exception as e:
        _result("lcd", str(e), False)
        return False


def _check_button(wait_s=3):
    try:
        import M5
        M5.begin()
        M5.BtnA.isPressed()
        _result("button_api", "BtnA", True)
        print("# press BtnA within %ds (short); hold ~1s for long" % wait_s)
        t0 = time.ticks_ms()
        saw_short = False
        saw_long = False
        hold = 0
        while time.ticks_diff(time.ticks_ms(), t0) < wait_s * 1000:
            M5.update()
            if M5.BtnA.wasPressed():
                saw_short = True
            if M5.BtnA.isPressed():
                if hold == 0:
                    hold = time.ticks_ms()
                elif time.ticks_diff(time.ticks_ms(), hold) > 800:
                    saw_long = True
                    break
            else:
                hold = 0
            time.sleep_ms(20)
        _result("button_short", saw_short, saw_short)
        _result("button_long", saw_long, saw_long)
        return saw_short or saw_long
    except Exception as e:
        _result("button_api", str(e), False)
        return False


def _check_nfc():
    import machine
    from pn532 import PN532
    pins = [(4, 5), (5, 4), (22, 23)]
    for sda, scl in pins:
        try:
            i2c = machine.SoftI2C(
                sda=machine.Pin(sda), scl=machine.Pin(scl), freq=100_000)
            nfc = PN532(i2c, 0x24)
            fw = nfc.begin()
            _result("nfc_pins", "sda=%d scl=%d" % (sda, scl), True)
            _result("nfc_fw", "%d.%d" % (fw[1], fw[2]), True)
            tag = nfc.read_passive_target(timeout=500)
            if tag:
                _result("nfc_uid", tag['uid_hex'], True)
            else:
                _result("nfc_uid", "none_tap_card", True)
            return True
        except Exception:
            continue
    _result("nfc_pins", "all_failed", False)
    return False


def run():
    print("# probe_stick start")
    _check_lcd()
    ap_ok = _check_ap_socket()
    nfc_ok = _check_nfc()
    _check_button(5)
    all_ok = ap_ok and nfc_ok
    _result("probe_pass", all_ok, all_ok)
    print("# probe_stick done — see RESULT lines above")
