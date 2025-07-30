import os
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

def run_http_server():
    port = int(os.environ.get("PORT", 8001))
    httpd = HTTPServer(('0.0.0.0', port), SimpleHandler)
    print(f"HTTP server running on port {port}")
    httpd.serve_forever()

def run_celery_worker():
    os.system("celery -A app.celery_app worker --loglevel=info -Q ai_processing --pool=solo")

if __name__ == "__main__":
    # Start HTTP server in a thread (keeps port open for Render)
    http_thread = Thread(target=run_http_server, daemon=True)
    http_thread.start()

    # Run Celery worker (blocking, so logs appear in output)
    run_celery_worker()
