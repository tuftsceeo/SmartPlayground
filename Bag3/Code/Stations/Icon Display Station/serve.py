#!/usr/bin/env python3
"""
serve.py -- dev server for the Icon Maker web app.

Exists because `python3 -m http.server` lets Chrome cache ES modules
aggressively: `index.html` carries a `?v=N` cache-buster but the modules it
imports do not, so editing e.g. js/pipeline/ledcolor.js and reloading gives
you a stale module and a confusing "does not provide an export named ..."
error. Hard-reloading every time is a bad workflow; sending no-store is the
actual fix.

    python3 serve.py            # http://localhost:8757/webapp/
    python3 serve.py 9000       # different port

Web Serial needs a secure context -- localhost qualifies, so this is fine.
"""

import sys
import http.server
import socketserver

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8757


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        # Quieter: skip the 200s, keep anything that went wrong.
        msg = fmt % args
        if " 200 " not in msg and " 304 " not in msg:
            sys.stderr.write("%s\n" % msg)


class ReusableServer(socketserver.TCPServer):
    allow_reuse_address = True  # avoids "Address already in use" on quick restarts


if __name__ == "__main__":
    with ReusableServer(("", PORT), NoCacheHandler) as httpd:
        print(f"Icon Maker dev server -> http://localhost:{PORT}/webapp/")
        print("(no-store headers set, so a plain reload always picks up edits)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
