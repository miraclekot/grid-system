#!/usr/bin/env python3
from pathlib import Path
import asyncio
from typing import List, Dict, Optional
from aiohttp import web

from grid_system_common import Placement, Subproblem, WorkerStatus
from .generator import Generator
from .dispatcher import Dispatcher
from .config import Config
from .log_manager import LogManager
from .storage import PersistentStorage
from .console import Console

# Определение корневой директории проекта
PROJECT_ROOT = Path(__file__).parent.parent.parent
MASTER_ROOT = Path(__file__).parent.parent

class Master:
    def __init__(self, config):
        self.config = config
        self.matrix = None
        self.words = None
        self.generator = None
        self.dispatcher = None
        self.subproblems: Dict[int, Subproblem] = {}
        self.results: Dict[int, List[Placement]] = {}
        self.computation_started = False
        self.computation_done = False
        self.final_placements = []
        
        # Инициализация сервисов
        self.log_manager = LogManager(MASTER_ROOT / "master_node" / "_logs")
        self.storage = PersistentStorage(MASTER_ROOT / "master_node" / "_processing")
        
        # Логгеры
        self.logger = self.log_manager.get_logger("master")
        self.generator_logger = self.log_manager.get_logger("generator")
        self.dispatcher_logger = self.log_manager.get_logger("dispatcher")
    
    def load_matrix(self, path):
        with open(path, 'r') as f:
            lines = f.read().strip().splitlines()
            if not lines:
                raise ValueError("Empty matrix file")
            h, w = map(int, lines[0].split())
            matrix = [list(line.strip()) for line in lines[1:1+h]]
            if len(matrix) != h or any(len(row) != w for row in matrix):
                raise ValueError("Matrix dimensions do not match header")
            self.matrix = matrix
        self.logger.info(f"Matrix loaded: {h}x{w}")
        return matrix
    
    def load_words(self, path):
        with open(path, 'r') as f:
            self.words = [line.strip() for line in f if line.strip()]
        self.logger.info(f"Words loaded: {len(self.words)} words")
        return self.words
    
    async def start_computation(self):
        if self.computation_started:
            self.logger.warning("Computation already started")
            return
        
        self.computation_started = True
        self.computation_done = False
        self.logger.info("Starting computation")
        
        try:
            # Загружаем сохраненное состояние
            completed = self.storage.load_completed_subtasks()
            saved_results = self.storage.load_results()
            self.results.update(saved_results)
            self.logger.info(f"Loaded {len(completed)} completed subtasks from storage")
            
            # Создаем генератор и вычисляем размещения
            self.generator = Generator(self.matrix, self.words, self.config.coefficient)
            await asyncio.to_thread(self.generator.compute_placement_counts)
            self.generator.create_subproblems()
            
            # Сохраняем подзадачи
            self.subproblems = {sub.id: sub for sub in self.generator.subproblems}
            self.storage.save_subproblems(self.subproblems)
            self.logger.info(f"Created {len(self.subproblems)} subproblems")
            
            # Запускаем диспетчер
            self.dispatcher = Dispatcher(self.config, self.matrix, self.log_manager)
            await self.dispatcher.start()
            
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
            await asyncio.gather(*tasks, return_exceptions=True)
            
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
        try:
            placements = await self.dispatcher.submit_subproblem(subproblem)
            self.results[subproblem.id] = placements
            self.storage.save_completed_subtask(subproblem.id)
            self.storage.save_results(self.results)
            self.logger.info(f"Subproblem {subproblem.id} solved with {len(placements)} placements")
        except Exception as e:
            self.logger.error(f"Subproblem {subproblem.id} failed: {e}")
            self.results[subproblem.id] = []
    
    def compute_covering(self, all_placements: List[Placement]):
        """Жадный алгоритм покрытия."""
        if not all_placements:
            return []
        
        total_cells = len(self.matrix) * len(self.matrix[0])
        covered = set()
        selected = []
        remaining = all_placements[:]
        
        while len(covered) < total_cells and remaining:
            best = None
            best_new = 0
            for p in remaining:
                new_cells = set(p.cells) - covered
                if len(new_cells) > best_new:
                    best_new = len(new_cells)
                    best = p
            if best_new == 0:
                break
            selected.append(best)
            covered.update(best.cells)
            remaining.remove(best)
        
        return selected
    
    def get_status(self):
        """Получить текущий статус вычислений."""
        worker_status = self.dispatcher.get_worker_status() if self.dispatcher else {}
        return {
            "started": self.computation_started,
            "done": self.computation_done,
            "subproblems_total": len(self.subproblems),
            "subproblems_solved": len(self.results),
            "subproblems_pending": len(self.subproblems) - len(self.results),
            "final_placements_count": len(self.final_placements),
            "covered_cells": len(set(cell for p in self.final_placements for cell in p.cells)),
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

async def master_http_handler(master: Master):
    """HTTP обработчик для взаимодействия с воркерами."""
    app = web.Application()
    app['master'] = master
    
    async def register(request):
        data = await request.json()
        address = data['address']
        worker_id = await master.dispatcher.register_worker(address)
        master.dispatcher_logger.info(f"Worker {worker_id} registered from {address}")
        return web.json_response({'worker_id': worker_id})
    
    async def heartbeat(request):
        data = await request.json()
        worker_id = data['worker_id']
        status = WorkerStatus(data['status'])
        current_task = data.get('current_task')
        await master.dispatcher.update_heartbeat(worker_id, status, current_task)
        master.dispatcher_logger.debug(f"Heartbeat from worker {worker_id}: {status.value}")
        return web.Response(status=200)
    
    async def workers_status(request):
        status = master.dispatcher.get_worker_status()
        return web.json_response(status)
    
    app.router.add_post('/register', register)
    app.router.add_post('/heartbeat', heartbeat)
    app.router.add_get('/workers', workers_status)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, master.config.master_host, master.config.master_port)
    await site.start()
    
    master.logger.info(f"Master HTTP server started on {master.config.master_host}:{master.config.master_port}")
    return runner

async def main():
    """Главная функция."""
    print("\n" + "="*60)
    print("     ГРИД-СИСТЕМА - MASTER NODE")
    print("="*60)
    
    config = Config()
    
    # Ввод параметров
    config.matrix_path = input("Путь к файлу матрицы: ").strip()
    config.words_path = input("Путь к файлу словаря: ").strip()
    try:
        config.coefficient = int(input("Коэффициент сложности: ").strip())
    except ValueError:
        print("Используется коэффициент по умолчанию: 1000")
        config.coefficient = 1000
    
    master = Master(config)
    
    try:
        master.load_matrix(config.matrix_path)
        master.load_words(config.words_path)
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}")
        return
    
    # Запуск HTTP сервера для воркеров
    try:
        http_runner = await master_http_handler(master)
    except Exception as e:
        print(f"Ошибка запуска HTTP сервера: {e}")
        return
    
    # Запуск консоли
    console = Console(master)
    try:
        await console.run()
    except KeyboardInterrupt:
        print("\nПолучен сигнал прерывания...")
    finally:
        if master.dispatcher:
            await master.dispatcher.stop()
        await http_runner.cleanup()
    
    print("Master node остановлен.")

if __name__ == "__main__":
    asyncio.run(main())