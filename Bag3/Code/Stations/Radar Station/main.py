"""
main.py -- boots the JSON-over-serial radar server. Mirrors the Icon
Display Station's main.py: never let a bare traceback hit stdout, since
the browser's line filter drops any line not starting with '{', which
would make an unguarded traceback look like a silent hang rather than a
visible error. Ship it IN BAND as JSON instead.
"""

DEBUG = False

try:
    from radar_server import RadarServer
    RadarServer(debug=DEBUG).run()
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
