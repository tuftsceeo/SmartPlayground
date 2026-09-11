"""
main.py -- the icon display station.

Runs two things at once on one 16x16 panel:

  * the JSON-over-serial icon server, which is how icons are authored and how
    ChatBroadcast writes files to this station (see icon_server.py);
  * a gamelib.Device, which is how the station takes part in a game -- it
    answers "cap" commands from a wand and runs its own role file out of
    /games when a "sys start" names a game it holds.

Both draw through a single icon_matrix.Matrix. One NeoPixel object per strip:
two would fight over the same pin.

The USB link stays alive while a game runs, because dev.on_pump services it on
every pass of the game loop. That is what lets a teacher keep editing icons
with a game running.

Never let a bare traceback hit stdout: the browser's line filter drops any line
not starting with '{', so an unguarded traceback would look like a silent hang
rather than a visible error. Ship it IN BAND as JSON instead.
"""

DEBUG = False

# How long the idle loop waits on the USB link with nothing arriving. This is
# what paces the loop; the radio is polled once per pass.
IDLE_MS = 20


def main():
    from hubtype import HUB_TYPE
    from espnow_manager import ESPNowManager
    from icon_matrix import Matrix, DEFAULT_INTENSITY
    from icon_server import IconServer
    from panel import IconPanel
    import gamelib

    print("# icon display station -- hubtype %s" % HUB_TYPE)

    # Radio first, before anything else allocates: esp_wifi_init() needs tens
    # of KB of contiguous IDF heap and MicroPython never returns a split back
    # to it. The wand's main.py orders its boot the same way and for the same
    # measured reason.
    net = ESPNowManager()
    net.init()

    matrix = Matrix(intensity=DEFAULT_INTENSITY)
    panel = IconPanel(matrix)
    server = IconServer(debug=DEBUG, matrix=matrix)

    dev = gamelib.Device(net)
    dev.matrix = matrix
    dev.icon = panel      # what a game calls: dev.icon.show("tree")
    dev.cap = panel       # what a wand's "cap" message reaches
    def service_usb():
        """One USB pass per game-loop pass, so authoring survives a game.

        idle_ms=0 keeps it non-blocking: a game's frame rate must not be paced
        by the serial link. A `repl` or `reboot` command ends the game too,
        otherwise the request would wait for the game to finish.
        """
        server.step(idle_ms=0)
        if not server.running:
            dev.stop()

    dev.on_pump = service_usb

    server.start()
    try:
        while server.running:
            server.step(idle_ms=IDLE_MS)
            dev.pump()
            dev.step_cap()
            action = dev.take_exit()
            if isinstance(action, tuple):
                slug = action[1]
                # The authoring cycle and a game both drive the panel; the game
                # wins for as long as it runs.
                server.cycle_on = False
                print("# starting game %s" % slug)
                dev.launch(slug)
                print("# game %s ended" % slug)
    except KeyboardInterrupt:
        server.link.send({"type": "bye"})
    finally:
        server.finish()


try:
    main()
except KeyboardInterrupt:
    pass
except Exception as e:
    import io
    import sys
    import json
    b = io.StringIO()
    sys.print_exception(e, b)
    try:
        print(json.dumps({"type": "fatal", "msg": "%s: %s" % (type(e).__name__, e), "tb": b.getvalue()[-400:]}))
    except Exception:
        print('{"type":"fatal","msg":"unprintable error"}')

# falling off the end (KeyboardInterrupt, `repl`/`reboot` commands, or a
# caught fatal error) lands at the >>> prompt.
