import asyncio
import aiohttp
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import logging
from pathlib import Path

from grid_system_common import Subproblem, WorkerInfo, WorkerStatus, Placement

class Dispatcher:
    def __init__(self, config, matrix, log_manager):
        self.config = config
        self.matrix = matrix
        self.log_manager = log_manager
        self.logger = log_manager.get_logger("dispatcher")
        
        self.workers: Dict[int, WorkerInfo] = {}
        self.next_worker_id = 0
        self.pending_queue: asyncio.Queue = asyncio.Queue()
        self.futures: Dict[int, asyncio.Future] = {}
        self.subproblem_to_worker: Dict[int, int] = {}
        self.worker_task = None
        self.heartbeat_task = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
        self.lock = asyncio.Lock()
    
    async def start(self):
        """Запуск диспетчера."""
        self.session = aiohttp.ClientSession()
        self.running = True
        self.worker_task = asyncio.create_task(self._worker_loop())
        self.heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
        self.logger.info("Dispatcher started")
    
    async def stop(self):
        """Остановка диспетчера."""
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.session:
            await self.session.close()
        self.logger.info("Dispatcher stopped")
    
    async def register_worker(self, address: str) -> int:
        """Регистрация нового воркера."""
        async with self.lock:
            worker_id = self.next_worker_id
            self.next_worker_id += 1
            self.workers[worker_id] = WorkerInfo(
                id=worker_id,
                address=address,
                status=WorkerStatus.AVAILABLE
            )
            self.logger.info(f"Worker {worker_id} registered at {address}")
            return worker_id
    
    async def unregister_worker(self, worker_id: int):
        """Удаление воркера."""
        async with self.lock:
            if worker_id in self.workers:
                worker = self.workers[worker_id]
                worker.status = WorkerStatus.OFFLINE
                if worker.current_task is not None:
                    self.logger.warning(f"Worker {worker_id} died while processing task {worker.current_task}")
                    await self._reassign_task(worker.current_task)
                del self.workers[worker_id]
                self.logger.info(f"Worker {worker_id} unregistered")
    
    async def submit_subproblem(self, subproblem: Subproblem) -> List[Placement]:
        """Отправка подзадачи на выполнение."""
        future = asyncio.get_event_loop().create_future()
        self.futures[subproblem.id] = future
        await self.pending_queue.put(subproblem)
        self.logger.debug(f"Subproblem {subproblem.id} queued (complexity: {subproblem.complexity})")
        
        try:
            return await asyncio.wait_for(future, timeout=self.config.task_timeout)
        except asyncio.TimeoutError:
            self.logger.error(f"Subproblem {subproblem.id} timed out")
            await self._reassign_task(subproblem.id)
            raise
    
    async def update_heartbeat(self, worker_id: int, status: WorkerStatus, current_task: Optional[int]):
        """Обновление heartbeat воркера."""
        async with self.lock:
            if worker_id in self.workers:
                worker = self.workers[worker_id]
                worker.last_heartbeat = datetime.now()
                worker.status = status
                if status == WorkerStatus.BUSY and current_task is not None:
                    worker.current_task = current_task
                    self.logger.debug(f"Worker {worker_id} busy with task {current_task}")
                elif status == WorkerStatus.AVAILABLE:
                    worker.current_task = None
                    worker.task_start_time = None
    
    async def _worker_loop(self):
        """Основной цикл распределения задач."""
        while self.running:
            try:
                subproblem = await asyncio.wait_for(
                    self.pending_queue.get(),
                    timeout=self.config.dispatcher_poll_timeout
                )
                
                worker = await self._get_available_worker()
                if worker is None:
                    self.logger.debug("No available workers, requeuing task")
                    await self.pending_queue.put(subproblem)
                    await asyncio.sleep(self.config.no_worker_sleep)
                    continue
                
                await self._assign_task(worker, subproblem)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in worker loop: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def _get_available_worker(self) -> Optional[WorkerInfo]:
        """Поиск доступного воркера."""
        async with self.lock:
            for worker in self.workers.values():
                if worker.status == WorkerStatus.AVAILABLE:
                    if datetime.now() - worker.last_heartbeat < timedelta(seconds=30):
                        return worker
                    else:
                        worker.status = WorkerStatus.OFFLINE
                        self.logger.warning(f"Worker {worker.id} missed heartbeat, marking as offline")
            return None
    
    async def _assign_task(self, worker: WorkerInfo, subproblem: Subproblem):
        """Назначение задачи воркеру."""
        async with self.lock:
            worker.status = WorkerStatus.BUSY
            worker.current_task = subproblem.id
            worker.task_start_time = datetime.now()
            subproblem.assigned_worker = worker.id
            subproblem.status = "assigned"
            self.subproblem_to_worker[subproblem.id] = worker.id
        
        self.logger.info(f"Assigning subproblem {subproblem.id} to worker {worker.id}")
        asyncio.create_task(self._send_task_to_worker(worker, subproblem))
    
    async def _send_task_to_worker(self, worker: WorkerInfo, subproblem: Subproblem):
        """Отправка задачи воркеру и обработка ответа."""
        try:
            url = f"{worker.address}/task"
            payload = {
                "id": subproblem.id,
                "words": subproblem.words,
                "matrix": self.matrix
            }
            
            async with self.session.post(url, json=payload, timeout=self.config.task_timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    placements = []
                    for p in data['placements']:
                        placements.append(Placement(
                            word=p['word'],
                            row=p['row'],
                            col=p['col'],
                            dr=p['dr'],
                            dc=p['dc'],
                            cells=[tuple(cell) for cell in p['cells']]
                        ))
                    
                    future = self.futures.pop(subproblem.id, None)
                    if future:
                        future.set_result(placements)
                    
                    await self.update_heartbeat(worker.id, WorkerStatus.AVAILABLE, None)
                    self.logger.info(f"Subproblem {subproblem.id} completed by worker {worker.id} with {len(placements)} placements")
                else:
                    raise Exception(f"Worker returned status {resp.status}")
                    
        except asyncio.TimeoutError:
            self.logger.error(f"Worker {worker.id} timeout for subproblem {subproblem.id}")
            await self._handle_worker_failure(worker, subproblem.id)
        except Exception as e:
            self.logger.error(f"Worker {worker.id} failed: {e}")
            await self._handle_worker_failure(worker, subproblem.id)
    
    async def _handle_worker_failure(self, worker: WorkerInfo, subproblem_id: int):
        """Обработка отказа воркера."""
        await self.unregister_worker(worker.id)
        await self._reassign_task(subproblem_id)
    
    async def _reassign_task(self, subproblem_id: int):
        """Переназначение задачи."""
        self.logger.info(f"Reassigning subproblem {subproblem_id}")
        # В реальной реализации нужно восстановить Subproblem из хранилища
        # Здесь мы просто удаляем future, чтобы задача была пересоздана
        if subproblem_id in self.futures:
            future = self.futures.pop(subproblem_id, None)
            if future and not future.done():
                future.set_exception(Exception("Worker failed"))
        
        if subproblem_id in self.subproblem_to_worker:
            del self.subproblem_to_worker[subproblem_id]
    
    async def _heartbeat_monitor(self):
        """Мониторинг heartbeat воркеров."""
        while self.running:
            try:
                await asyncio.sleep(10)
                current_time = datetime.now()
                async with self.lock:
                    dead_workers = []
                    for worker_id, worker in self.workers.items():
                        if worker.status == WorkerStatus.BUSY:
                            if worker.task_start_time and \
                               current_time - worker.task_start_time > timedelta(seconds=self.config.task_timeout):
                                self.logger.warning(f"Worker {worker_id} task timeout, marking as dead")
                                dead_workers.append(worker_id)
                        elif worker.status == WorkerStatus.AVAILABLE:
                            if current_time - worker.last_heartbeat > timedelta(seconds=30):
                                self.logger.warning(f"Worker {worker_id} missed heartbeat, marking as dead")
                                dead_workers.append(worker_id)
                    
                    for worker_id in dead_workers:
                        await self.unregister_worker(worker_id)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in heartbeat monitor: {e}")
    
    def get_worker_status(self) -> Dict[int, dict]:
        """Получение статуса всех воркеров."""
        return {
            worker_id: {
                "id": worker.id,
                "address": worker.address,
                "status": worker.status.value,
                "current_task": worker.current_task,
                "last_heartbeat": worker.last_heartbeat.isoformat() if worker.last_heartbeat else None
            }
            for worker_id, worker in self.workers.items()
        }