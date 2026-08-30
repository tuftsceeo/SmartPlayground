"""
main.py — boots Broadcast Box firmware on M5Stack StickS3 (UIFlow2).

Writes to /flash. Never let a bare traceback hit stdout.
"""

DEBUG = False

try:
    from bbox_server import BboxServer
    BboxServer(debug=DEBUG).run()
except KeyboardInterrupt:
    pass
except Exception as e:
    import io
    import sys
    import json
    b = io.StringIO()
    sys.print_exception(e, b)
    try:
        print(json.dumps({
            "type": "fatal",
            "msg": "%s: %s" % (type(e).__name__, e),
            "tb": b.getvalue()[-400:],
        }))
    except Exception:
        print('{"type":"fatal","msg":"unprintable error"}')
