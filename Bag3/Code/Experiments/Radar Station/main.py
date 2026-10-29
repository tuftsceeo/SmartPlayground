"""
main.py -- boots the JSON-over-serial radar server. Catches all
exceptions and reports them as a JSON `fatal` line instead of a raw
traceback, so the browser's '{' line filter doesn't drop the error.
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
