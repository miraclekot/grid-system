from pathlib import Path


class Router:
    """Простой класс для маршрутизации"""
    def __init__(self):
        self.routes = {}
    
    def add_route(self, path, handler):
        self.routes[path] = handler
    
    def get_handler(self, path):
        return self.routes.get(path)
    
    def serve_static_file(self, path):
        """Подача статического файла из папки static"""
        # Убираем ведущий слеш и получаем путь к файлу
        file_path = path.lstrip('/')
        
        # Если путь начинается с static/ или это просто файл
        full_path = Path(self.static_dir) / file_path
        
        # Проверяем, существует ли файл и не выходит ли он за пределы static_dir
        try:
            full_path = full_path.resolve()
            static_dir_resolved = Path(self.static_dir).resolve()
            
            if full_path.is_file() and str(full_path).startswith(str(static_dir_resolved)):
                return full_path
        except:
            pass
        
        return None