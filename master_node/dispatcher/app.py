from http.server import BaseHTTPRequestHandler

from master_node.src.router import Router


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Проверяем, есть ли маршрут для этого пути
        handler = app.get_handler(self.path)
        
        if handler:
            response = handler()
            self.send_response(response['status'])
            self.send_header('Content-type', response['content_type'])
            self.end_headers()
            self.wfile.write(response['content'].encode('utf-8'))
        else:
            # Если маршрута нет, пытаемся подать статический файл
            static_file = app.serve_static(self.path)
            
            if static_file:
                # Определяем тип файла по расширению
                content_type = self.get_content_type(static_file)
                
                try:
                    with open(static_file, 'rb') as f:
                        content = f.read()
                    
                    self.send_response(200)
                    self.send_header('Content-type', content_type)
                    self.end_headers()
                    self.wfile.write(content)
                except Exception as e:
                    self.send_error(500, f"Ошибка при чтении файла: {e}")
            else:
                self.send_error(404, f"Путь {self.path} не найден")
                
    def get_content_type(self, file_path):
        """Определяем MIME тип файла по расширению"""
        ext = os.path.splitext(file_path)[1].lower()
        mime_types = {
            '.html': 'text/html; charset=utf-8',
            '.css': 'text/css; charset=utf-8',
            '.js': 'application/javascript; charset=utf-8',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
            '.json': 'application/json',
            '.txt': 'text/plain; charset=utf-8',
            '.pdf': 'application/pdf',
        }
        return mime_types.get(ext, 'application/octet-stream')
    
    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")


class App:
    def __init__(self):
        self.router = Router()
    
    def route(self, path):
        def decorator(handler):
            self.router.add_route(path, handler)
            return handler
        return decorator
    
    def get_handler(self, path):
        return self.router.get_handler(path)
    
    def serve_static(self, path):
        return self.router.serve_static_file(path)


app = App()

# Определяем маршруты через декораторы
@app.route('/')
def index_handler():
    try:
        with open('static/index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        return {
            'status': 200,
            'content_type': 'text/html; charset=utf-8',
            'content': html_content
        }
    except FileNotFoundError:
        return {
            'status': 404,
            'content_type': 'text/html; charset=utf-8',
            'content': """
            <!DOCTYPE html>
            <html>
            <head><title>404 Не найдено</title></head>
            <body>
                <h1>404 Запрашиваемый ресурс не найден</h1>
            </body>
            </html>
            """
        }


