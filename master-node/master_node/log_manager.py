import logging
import logging.handlers
from pathlib import Path
from typing import List, Tuple, Dict


class LogManager:
    """Управление логами для различных компонентов."""
    
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.loggers: Dict[str, logging.Logger] = {}
        self._setup_loggers()
    
    def _setup_loggers(self):
        """Настройка логгеров для каждого компонента."""
        components = ['master', 'generator', 'dispatcher']
        for component in components:
            logger = logging.getLogger(f"grid_system.{component}")
            logger.setLevel(logging.DEBUG)
            
            # Очищаем существующие обработчики
            logger.handlers.clear()
            
            # Файловый обработчик
            log_file = self.log_dir / f"{component}.log"
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            
            # Форматтер
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            
            logger.addHandler(file_handler)
            self.loggers[component] = logger
    
    def get_logger(self, component: str) -> logging.Logger:
        """Получить логгер для компонента."""
        return self.loggers.get(component, logging.getLogger(f"grid_system.{component}"))
    
    def read_log(self, component: str, lines: int = 50, offset: int = 0) -> Tuple[List[str], int, bool]:
        """
        Чтение лога с поддержкой пагинации.
        Возвращает: (строки, общее_количество_строк, достигнут_ли_конец)
        """
        log_file = self.log_dir / f"{component}.log"
        if not log_file.exists():
            return [], 0, True
        
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        total_lines = len(all_lines)
        end_reached = (offset + lines) >= total_lines
        
        start = offset
        end = min(offset + lines, total_lines)
        return all_lines[start:end], total_lines, end_reached