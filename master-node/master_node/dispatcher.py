# dispatcher.py
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
        
        self.logger.info("Dispatcher initialized")
    
    async def start(self):
        """Запуск диспетчера."""
        if self.running:
            self.logger.warning("Dispatcher already running")
            return
            
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
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        if self.session:
            await self.session.close()
        self.logger.info("Dispatcher stopped")
    
    async def register_worker(self, address: str) -> int:
        """Регистрация нового воркера."""
        async with self.lock:
            worker_id = self.next_worker_id
            self.next_worker_id += 1
            
            # Явно устанавливаем last_heartbeat            
            self.workers[worker_id] = WorkerInfo(
                id=worker_id,
                address=address,
                status=WorkerStatus.AVAILABLE,
                last_heartbeat=datetime.now(),
            )
            self.logger.info(f"Worker {worker_id} registered at {address}")
            return worker_id
    
    async def unregister_worker(self, worker_id: int):
        """Удаление воркера."""
        async with self.lock:
            if worker_id in self.workers:
                worker = self.workers[worker_id]
                self.logger.info(f"Unregistering worker {worker_id} (status: {worker.status.value})")
                
                # Если у воркера была задача, переназначаем её
                if worker.current_task is not None:
                    self.logger.warning(f"Worker {worker_id} died while processing task {worker.current_task}")
                    await self._reassign_task(worker.current_task)
                
                # Удаляем воркера из словарей
                del self.workers[worker_id]
                self.logger.info(f"Worker {worker_id} unregistered")
    
    async def submit_subproblem(self, subproblem: Subproblem) -> List[Placement]:
        """Отправка подзадачи на выполнение."""
        if not self.running:
            raise RuntimeError("Dispatcher not running")
            
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
            if worker_id not in self.workers:
                self.logger.warning(f"Heartbeat from unknown worker {worker_id}")
                return
            
            worker = self.workers[worker_id]
            worker.last_heartbeat = datetime.now()
            worker.status = status
            
            self.logger.debug(f"Worker {worker_id} heartbeat at {worker.last_heartbeat}, status: {status.value}")            
            
            if status == WorkerStatus.BUSY and current_task is not None:
                worker.current_task = current_task
                self.logger.debug(f"Worker {worker_id} busy with task {current_task}")
            elif status == WorkerStatus.AVAILABLE:
                worker.current_task = None
                worker.task_start_time = None
            elif status == WorkerStatus.OFFLINE:
                self.unregister_worker(worker_id)
    
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
            current_time = datetime.now()
            available_workers = []
            
            for worker in self.workers.values():
                # Проверяем, что воркер активен (heartbeat не старше 30 секунд)
                time_since_heartbeat = (current_time - worker.last_heartbeat).total_seconds()
                is_alive = time_since_heartbeat < 30
                
                self.logger.debug(
                    f"Worker {worker.id}: status={worker.status.value}, "
                    f"last_heartbeat={time_since_heartbeat:.1f}s ago, is_alive={is_alive}"
                )
                
                if worker.status == WorkerStatus.AVAILABLE and is_alive:
                    available_workers.append(worker)
                elif not is_alive and worker.status != WorkerStatus.OFFLINE:
                    # Воркер не отвечает, помечаем как OFFLINE
                    self.logger.warning(
                        f"Worker {worker.id} missed heartbeat for {time_since_heartbeat:.1f}s, "
                        f"marking as offline"
                    )
                    worker.status = WorkerStatus.OFFLINE
            
            if not available_workers:
                return None
            
            return available_workers[0]
    
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
                    error_msg = f"Worker returned status {resp.status}"
                    self.logger.error(error_msg)
                    raise Exception(error_msg)
                    
        except asyncio.TimeoutError:
            self.logger.error(f"Worker {worker.id} timeout for subproblem {subproblem.id}")
            await self._handle_worker_failure(worker, subproblem.id)
        except aiohttp.ClientConnectorError as e:
            self.logger.error(f"Cannot connect to worker {worker.id}: {e}")
            await self._handle_worker_failure(worker, subproblem.id)
        except Exception as e:
            self.logger.error(f"Worker {worker.id} failed: {e}")
            await self._handle_worker_failure(worker, subproblem.id)
    
    async def _handle_worker_failure(self, worker: WorkerInfo, subproblem_id: int):
        """Обработка отказа воркера."""
        self.logger.warning(f"Handling failure of worker {worker.id}")
        await self.unregister_worker(worker.id)
        await self._reassign_task(subproblem_id)
    
    async def _reassign_task(self, subproblem_id: int):
        """Переназначение задачи."""
        self.logger.info(f"Reassigning subproblem {subproblem_id}")
        
        async with self.lock:
            if subproblem_id in self.futures:
                if subproblem_id in self.subproblem_to_worker:
                    del self.subproblem_to_worker[subproblem_id]
                
                self.logger.info(f"Subproblem {subproblem_id} will be retried")
    
    async def _heartbeat_monitor(self):
        """Мониторинг heartbeat воркеров."""
        while self.running:
            try:
                await asyncio.sleep(10)  # Проверяем каждые 10 секунд
                current_time = datetime.now()
                
                async with self.lock:
                    dead_workers = []
                    
                    for worker_id, worker in list(self.workers.items()):
                        time_since_heartbeat = (current_time - worker.last_heartbeat).total_seconds()
                        
                        # Проверяем, что heartbeat не старше 30 секунд
                        if time_since_heartbeat > 30:
                            self.logger.warning(
                                f"Worker {worker_id} missed heartbeat for {time_since_heartbeat:.1f}s, "
                                f"status: {worker.status.value}, task: {worker.current_task}"
                            )
                            dead_workers.append(worker_id)
                        
                        # Для BUSY воркеров также проверяем таймаут задачи
                        elif worker.status == WorkerStatus.BUSY and worker.task_start_time:
                            task_duration = (current_time - worker.task_start_time).total_seconds()
                            if task_duration > self.config.task_timeout:
                                self.logger.warning(
                                    f"Worker {worker_id} task timeout ({task_duration:.1f}s > {self.config.task_timeout}s), "
                                    f"task: {worker.current_task}"
                                )
                                dead_workers.append(worker_id)
                    
                    # Удаляем мертвых воркеров
                    for worker_id in dead_workers:
                        await self.unregister_worker(worker_id)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in heartbeat monitor: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    def get_worker_status(self) -> Dict[int, dict]:
        """
        Получение статуса всех воркеров.
        Это синхронный метод, так как только читает данные.
        """
        result = {}
        current_time = datetime.now()
        
        # Копируем словарь для безопасного чтения
        workers_copy = dict(self.workers)
        
        for worker_id, worker in workers_copy.items():
            time_since_heartbeat = (current_time - worker.last_heartbeat).total_seconds()
            is_alive = time_since_heartbeat < 30
            
            # Определяем отображаемый статус
            if is_alive:
                # Если воркер жив, показываем его реальный статус
                status_display = worker.status.value
            else:
                # Если воркер не отвечает, показываем OFFLINE
                status_display = WorkerStatus.OFFLINE.value
            
            result[worker_id] = {
                "id": worker.id,
                "address": worker.address,
                "status": status_display,
                "current_task": worker.current_task,
                "last_heartbeat": worker.last_heartbeat.isoformat() if worker.last_heartbeat else None,
                "heartbeat_seconds_ago": int(time_since_heartbeat),
                "is_alive": is_alive
            }
        
        return result
    
    def get_worker_count(self) -> Dict[str, int]:
        """Получение статистики по воркерам (синхронный метод)."""
        current_time = datetime.now()
        
        available = 0
        busy = 0
        offline = 0
        
        for worker in self.workers.values():
            time_since_heartbeat = (current_time - worker.last_heartbeat).total_seconds()
            is_alive = time_since_heartbeat < 30
            
            if not is_alive:
                offline += 1
            elif worker.status == WorkerStatus.AVAILABLE:
                available += 1
            elif worker.status == WorkerStatus.BUSY:
                busy += 1
        
        return {
            "total": len(self.workers),
            "available": available,
            "busy": busy,
            "offline": offline
        }