"""
main.py -- boots the JSON-over-serial icon server. Replaces the old
cycling-prototype main.py (that behaviour is now the `cycle` command --
see icon_server.py). Full protocol reference: the top-level plan
("ESP32-C6 firmware") and webapp/README.md.

Never let a bare traceback hit stdout: the browser's line filter drops
any line not starting with '{', so an unguarded traceback would look like
a silent hang rather than a visible error. Ship it IN BAND as JSON instead.
"""

DEBUG = False

try:
    from icon_server import IconServer
    IconServer(debug=DEBUG).run()
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
