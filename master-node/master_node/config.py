class Config:
    """Конфигурация приложения."""
    
    def __init__(self):
        self.matrix_path = ""
        self.words_path = ""
        self.coefficient = 1000
        self.worker_timeout = 30.0
        self.task_timeout = 60.0
        self.dispatcher_poll_timeout = 1.0
        self.no_worker_sleep = 5.0
        self.master_host = "127.0.0.1"
        self.master_port = 8080
    
    def load(self, path: str):
        """Загрузка конфигурации из файла."""
        # Можно реализовать загрузку из JSON/YAML
        pass
    
    def save(self, path: str):
        """Сохранение конфигурации в файл."""
        pass