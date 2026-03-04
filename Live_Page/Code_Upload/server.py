from http.server import HTTPServer, SimpleHTTPRequestHandler

class IsolatedHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        super().end_headers()

print("Serving at http://localhost:8000")
HTTPServer(("", 8000), IsolatedHandler).serve_forever()