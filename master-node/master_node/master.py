#!/usr/bin/env python3
# master.py
from pathlib import Path
import asyncio
from typing import List, Dict, Optional
from aiohttp import web

from grid_system_common import Placement, Subproblem, WorkerStatus
from master_node.generator import Generator
from master_node.dispatcher import Dispatcher
from master_node.config import Config
from master_node.log_manager import LogManager
from master_node.storage import PersistentStorage


class Master:
    def __init__(self, config: Config):
        self.config = config
        self.matrix = None
        self.words = None
        self.generator = None
        self.dispatcher: Optional[Dispatcher] = None  # Явно указываем тип
        self.subproblems: Dict[int, Subproblem] = {}
        self.results: Dict[int, List[Placement]] = {}
        self.computation_started = False
        self.computation_done = False
        self.final_placements = []
        
        # Инициализация директорий
        self.master_dir = Path(__file__).parent
        self.logs_dir = self.master_dir / "_logs"
        self.processing_dir = self.master_dir / "_processing"
        
        # Инициализация сервисов
        self.log_manager = LogManager(self.logs_dir)
        self.storage = PersistentStorage(self.processing_dir)
        
        # Логгеры
        self.logger = self.log_manager.get_logger("master")
        
        # Инициализация диспетчера (без matrix, она будет установлена позже)
        try:
            self.dispatcher = Dispatcher(self.config, self.matrix, self.log_manager)
            self.logger.info("Dispatcher initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize dispatcher: {e}")
            raise
    
    def load_matrix(self, path: str):
        """Загрузка матрицы из файла."""
        with open(path, 'r', encoding='utf-8') as f:
            # Читаем все строки, удаляем пустые
            lines = [line.strip() for line in f.readlines() if line.strip()]
            
            if not lines:
                raise ValueError("Empty matrix file")
            
            # Парсим матрицу: каждая строка содержит буквы, разделенные пробелами
            matrix = []
            for line in lines:
                # Разделяем по пробелам и удаляем пустые элементы
                row = [ch for ch in line.split() if ch]
                if row:
                    matrix.append(row)
            
            # Проверяем, что все строки одинаковой длины
            if not matrix:
                raise ValueError("Matrix is empty after parsing")
            
            width = len(matrix[0])
            for i, row in enumerate(matrix):
                if len(row) != width:
                    raise ValueError(f"Row {i} has {len(row)} columns, expected {width}")
            
            self.matrix = matrix
            # Обновляем матрицу в диспетчере
            if self.dispatcher:
                self.dispatcher.matrix = matrix
                self.logger.debug("Matrix updated in dispatcher")
        
        self.logger.info(f"Matrix loaded: {len(self.matrix)}x{len(self.matrix[0])}")
        return self.matrix
    
    def load_words(self, path: str):
        """Загрузка слов из файла."""
        with open(path, 'r', encoding='utf-8') as f:
            # Читаем все строки, удаляем пустые и лишние пробелы
            self.words = [line.strip() for line in f.readlines() if line.strip()]
        
        self.logger.info(f"Words loaded: {len(self.words)} words")
        return self.words
    
    async def start_computation(self):
        """Запуск вычислений."""
        if self.computation_started:
            self.logger.warning("Computation already started")
            return
        
        if self.dispatcher is None:
            raise RuntimeError("Dispatcher not initialized")
        
        self.computation_started = True
        self.computation_done = False
        self.logger.info("Starting computation")
        
        try:
            # Проверяем, что матрица и слова загружены
            if not self.matrix:
                raise ValueError("Matrix not loaded")
            if not self.words:
                raise ValueError("Words not loaded")
            
            # Загружаем сохраненное состояние
            completed = self.storage.load_completed_subtasks()
            saved_results = self.storage.load_results()
            self.results.update(saved_results)
            self.logger.info(f"Loaded {len(completed)} completed subtasks from storage")
            
            # Создаем генератор и вычисляем размещения
            self.generator = Generator(self.matrix, self.words, self.config.coefficient, self.log_manager)
            await asyncio.to_thread(self.generator.compute_placement_counts)
            self.generator.create_subproblems()
            
            # Сохраняем подзадачи
            self.subproblems = {sub.id: sub for sub in self.generator.subproblems}
            self.storage.save_subproblems(self.subproblems)
            self.logger.info(f"Created {len(self.subproblems)} subproblems")
            
            # Обновляем матрицу в диспетчере (на всякий случай)
            if self.dispatcher:
                self.dispatcher.matrix = self.matrix
            
            # Запускаем диспетчер (если еще не запущен)
            if not self.dispatcher.running:
                await self.dispatcher.start()
                self.logger.info("Dispatcher started")
            
            # Обрабатываем только невыполненные подзадачи
            pending_subproblems = [
                sub for sub in self.generator.subproblems 
                if sub.id not in completed
            ]
            self.logger.info(f"Processing {len(pending_subproblems)} pending subproblems")
            
            tasks = []
            for sub in pending_subproblems:
                task = asyncio.create_task(self._process_subproblem(sub))
                tasks.append(task)
            
            # Ждем завершения всех задач
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Проверяем наличие ошибок
            for result in results:
                if isinstance(result, Exception):
                    self.logger.error(f"Task failed: {result}")
            
            # Сохраняем результаты
            self.storage.save_results(self.results)
            
            # Вычисляем финальное покрытие
            all_placements = []
            for placements in self.results.values():
                all_placements.extend(placements)
            self.final_placements = self.compute_covering(all_placements)
            
            self.computation_done = True
            self.logger.info(f"Computation completed. Selected {len(self.final_placements)} placements")
            
        except Exception as e:
            self.logger.error(f"Computation failed: {e}", exc_info=True)
            raise
    
    async def _process_subproblem(self, subproblem: Subproblem):
        """Обработка одной подзадачи."""
        if self.dispatcher is None:
            raise RuntimeError("Dispatcher not initialized")
        
        try:
            placements = await self.dispatcher.submit_subproblem(subproblem)
            self.results[subproblem.id] = placements
            self.storage.save_completed_subtask(subproblem.id)
            self.storage.save_results(self.results)
            self.logger.info(f"Subproblem {subproblem.id} solved with {len(placements)} placements")
            return placements
        except Exception as e:
            self.logger.error(f"Subproblem {subproblem.id} failed: {e}")
            self.results[subproblem.id] = []
            raise
    
    def compute_covering(self, all_placements: List[Placement]) -> List[Placement]:
        """Жадный алгоритм покрытия."""
        if not all_placements:
            return []
        
        total_cells = len(self.matrix) * len(self.matrix[0])
        covered = set()
        selected = []
        remaining = all_placements[:]
        
        # Сортируем по количеству клеток в размещении (убывание)
        remaining.sort(key=lambda p: len(p.cells), reverse=True)
        
        while len(covered) < total_cells and remaining:
            best = None
            best_new = 0
            
            # Ищем размещение, покрывающее максимальное количество новых клеток
            for p in remaining:
                new_cells = set(p.cells) - covered
                if len(new_cells) > best_new:
                    best_new = len(new_cells)
                    best = p
                if best_new == len(p.cells):  # Оптимальный вариант
                    break
            
            if best_new == 0:
                break
            
            selected.append(best)
            covered.update(best.cells)
            remaining.remove(best)
        
        self.logger.info(f"Covering completed: {len(covered)} cells covered with {len(selected)} placements")
        return selected
    
    def get_status(self) -> dict:
        """Получить текущий статус вычислений."""
        worker_status = self.dispatcher.get_worker_status() if self.dispatcher else {}
        
        total_cells = len(self.matrix) * len(self.matrix[0]) if self.matrix else 0
        covered_cells = len(set(cell for p in self.final_placements for cell in p.cells)) if self.final_placements else 0
        
        return {
            "started": self.computation_started,
            "done": self.computation_done,
            "subproblems_total": len(self.subproblems),
            "subproblems_solved": len(self.results),
            "subproblems_pending": len(self.subproblems) - len(self.results),
            "final_placements_count": len(self.final_placements),
            "total_cells": total_cells,
            "covered_cells": covered_cells,
            "uncovered_cells": total_cells - covered_cells,
            "workers": worker_status
        }
    
    def get_subproblem_info(self, sub_id: int) -> Optional[dict]:
        """Получить информацию о подзадаче."""
        sub = self.subproblems.get(sub_id)
        if not sub:
            return None
        solved = sub_id in self.results
        return {
            "id": sub.id,
            "words": sub.words,
            "complexity": sub.complexity,
            "solved": solved,
            "status": sub.status,
            "assigned_worker": sub.assigned_worker,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
            "solved_at": sub.solved_at.isoformat() if sub.solved_at else None,
            "placements_count": len(self.results.get(sub_id, []))
        }
    
    def get_matrix_display(self) -> str:
        """Получить матрицу для отображения."""
        if not self.matrix:
            return ""
        
        result = []
        for row in self.matrix:
            result.append(" ".join(row))
        return "\n".join(result)
    
    def get_covered_matrix_display(self) -> str:
        """Получить матрицу с отображением покрытых клеток."""
        if not self.matrix:
            return ""
        
        covered_cells = set()
        for p in self.final_placements:
            covered_cells.update(p.cells)
        
        result = []
        for r, row in enumerate(self.matrix):
            line = []
            for c, ch in enumerate(row):
                if (r, c) in covered_cells:
                    line.append(f"[{ch}]")
                else:
                    line.append(f" {ch} ")
            result.append(" ".join(line))
        
        return "\n".join(result)


async def master_http_handler(master: Master):
    """HTTP обработчик для взаимодействия с воркерами."""
    app = web.Application()
    app['master'] = master
    
    async def register(request):
        data = await request.json()
        address = data['address']
        
        # Проверяем, что dispatcher инициализирован
        if master.dispatcher is None:
            master.logger.error("Dispatcher not initialized")
            return web.Response(status=503, text="Dispatcher not initialized")
        
        try:
            worker_id = await master.dispatcher.register_worker(address)
            master.logger.info(f"Worker {worker_id} registered from {address}")
            return web.json_response({'worker_id': worker_id})
        except Exception as e:
            master.logger.error(f"Error registering worker: {e}")
            return web.Response(status=500, text=str(e))
    
    async def heartbeat(request):
        data = await request.json()
        worker_id = data['worker_id']
        status = WorkerStatus(data['status'])
        current_task = data.get('current_task')
        
        if master.dispatcher is None:
            master.logger.error("Dispatcher not initialized")
            return web.Response(status=503, text="Dispatcher not initialized")
        
        try:
            await master.dispatcher.update_heartbeat(worker_id, status, current_task)
            master.logger.debug(f"Heartbeat from worker {worker_id}: {status.value}")
            return web.Response(status=200)
        except Exception as e:
            master.logger.error(f"Error processing heartbeat: {e}")
            return web.Response(status=500, text=str(e))
    
    async def workers_status(request):
        if master.dispatcher is None:
            return web.json_response({})
        try:
            status = master.dispatcher.get_worker_status()
            return web.json_response(status)
        except Exception as e:
            master.logger.error(f"Error getting workers status: {e}")
            return web.json_response({})
    
    app.router.add_post('/register', register)
    app.router.add_post('/heartbeat', heartbeat)
    app.router.add_get('/workers', workers_status)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, master.config.master_host, master.config.master_port)
    await site.start()
    
    master.logger.info(f"Master HTTP server started on {master.config.master_host}:{master.config.master_port}")
    return runner