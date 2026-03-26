from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
from master_node.src.router import Router


def run_http_server(port):
    server = HTTPServer(('', port), RequestHandler)
    print(f"dispatcher запущен на http://localhost:{port}")
    server.serve_forever()


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        handler = app.get_handler(self.path)
        
        if handler:
            response = handler()
            self.send_response(response['status'])
            # Убираем charset из заголовка, оставляем только MIME тип
            content_type = response['content_type'].split(';')[0]
            self.send_header('Content-type', content_type)
            self.end_headers()
            
            content = response['content']
            if isinstance(content, str):
                self.wfile.write(content.encode('utf-8'))
            else:
                self.wfile.write(content)
        else:
            static_file = app.serve_static(self.path)
            
            if static_file:
                content_type = self.get_content_type(static_file)
                # Убираем charset если есть
                content_type = content_type.split(';')[0]
                
                try:
                    with open(static_file, 'rb') as f:
                        content = f.read()
                    
                    self.send_response(200)
                    self.send_header('Content-type', content_type)
                    self.end_headers()
                    self.wfile.write(content)
                except Exception as e:
                    self.send_error(500, f"Error reading file: {e}")
            else:
                self.send_error(404, f"Path {self.path} not found")
    
    def get_content_type(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        mime_types = {
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
            '.json': 'application/json',
            '.txt': 'text/plain',
            '.pdf': 'application/pdf',
        }
        return mime_types.get(ext, 'application/octet-stream')
    
    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")


class App:
    def __init__(self, static_dir):
        self.static_dir = static_dir
        self.router = Router(static_dir)
    
    def route(self, path):
        def decorator(handler):
            self.router.add_route(path, handler)
            return handler
        return decorator
    
    def get_handler(self, path):
        return self.router.get_handler(path)
    
    def serve_static(self, path):
        return self.router.serve_static_file(path)


app = App("master_node/static")

@app.route('/')
def index_handler():
    try:
        with open(os.path.join(app.static_dir, 'index.html'), 'r', encoding='utf-8') as f:
            html_content = f.read()
        return {
            'status': 200,
            'content_type': 'text/html',  # без charset
            'content': html_content
        }
    except FileNotFoundError:
        return {
            'status': 404,
            'content_type': 'text/html',
            'content': """
            <!DOCTYPE html>
            <html>
            <head><title>404 Not Found</title></head>
            <body>
                <h1>404 Requested resource not found</h1>
            </body>
            </html>
            """
        }