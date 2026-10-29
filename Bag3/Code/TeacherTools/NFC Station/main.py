"""main.py -- boots the NFC Station on an M5 Dial 2 (UIFlow2).

No radio is used, so nothing here has to precede a WiFi/ESP-NOW memory
claim. A fatal error is printed as one JSON line for the host.
"""

DEBUG = False

try:
    import M5
    M5.begin()

    import card_writer
    from dial_board import make_reader
    from dial_input import DialInput
    from json_link import JsonLink
    from station import Station
    from station_ui import StationUI

    inputs = DialInput()
    inputs.begin()
    ui = StationUI(inputs)
    ui.begin()
    station = Station(ui, inputs, make_nfc=make_reader, card=card_writer)
    station.link = JsonLink(station.dispatch, debug=DEBUG)
    station.run()
except KeyboardInterrupt:
    pass
except Exception as e:
    import io
    import sys
    import json
    b = io.StringIO()
    sys.print_exception(e, b)
    print(json.dumps({
        "type": "fatal",
        "msg": "%s: %s" % (type(e).__name__, e),
        "tb": b.getvalue()[-400:],
    }))
