import asyncio
import aiohttp
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import logging

from grid_system_common import Subproblem, WorkerInfo, WorkerStatus, Placement

logger = logging.getLogger(__name__)

class Dispatcher:
    def __init__(self, config, matrix):
        self.config = config
        self.matrix = matrix
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
        """Start dispatcher and background tasks."""
        self.session = aiohttp.ClientSession()
        self.running = True
        self.worker_task = asyncio.create_task(self._worker_loop())
        self.heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
        logger.info("Dispatcher started")

    async def stop(self):
        """Stop dispatcher and cleanup."""
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.session:
            await self.session.close()
        logger.info("Dispatcher stopped")

    async def register_worker(self, address: str) -> int:
        """Register a new worker."""
        async with self.lock:
            worker_id = self.next_worker_id
            self.next_worker_id += 1
            self.workers[worker_id] = WorkerInfo(
                id=worker_id,
                address=address,
                status=WorkerStatus.AVAILABLE
            )
            logger.info(f"Worker {worker_id} registered at {address}")
            return worker_id

    async def unregister_worker(self, worker_id: int):
        """Unregister a worker."""
        async with self.lock:
            if worker_id in self.workers:
                worker = self.workers[worker_id]
                worker.status = WorkerStatus.OFFLINE
                # Reassign any task this worker was processing
                if worker.current_task is not None:
                    await self._reassign_task(worker.current_task)
                del self.workers[worker_id]
                logger.info(f"Worker {worker_id} unregistered")

    async def submit_subproblem(self, subproblem: Subproblem) -> List[Placement]:
        """Submit a subproblem and wait for result."""
        future = asyncio.get_event_loop().create_future()
        self.futures[subproblem.id] = future
        await self.pending_queue.put(subproblem)
        
        try:
            return await asyncio.wait_for(future, timeout=self.config.task_timeout)
        except asyncio.TimeoutError:
            logger.error(f"Subproblem {subproblem.id} timed out")
            # Requeue on timeout
            await self._reassign_task(subproblem.id)
            raise

    async def update_heartbeat(self, worker_id: int, status: WorkerStatus, current_task: Optional[int]):
        """Update worker heartbeat."""
        async with self.lock:
            if worker_id in self.workers:
                worker = self.workers[worker_id]
                worker.last_heartbeat = datetime.now()
                worker.status = status
                if status == WorkerStatus.BUSY and current_task is not None:
                    worker.current_task = current_task
                elif status == WorkerStatus.AVAILABLE:
                    worker.current_task = None
                    worker.task_start_time = None

    async def _worker_loop(self):
        """Main worker distribution loop."""
        while self.running:
            try:
                # Get pending subproblem
                try:
                    subproblem = await asyncio.wait_for(
                        self.pending_queue.get(), 
                        timeout=self.config.dispatcher_poll_timeout
                    )
                except asyncio.TimeoutError:
                    continue

                # Find available worker
                worker = await self._get_available_worker()
                if worker is None:
                    # No available workers, put back and wait
                    await self.pending_queue.put(subproblem)
                    await asyncio.sleep(self.config.no_worker_sleep)
                    continue

                # Assign task to worker
                await self._assign_task(worker, subproblem)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                await asyncio.sleep(1)

    async def _get_available_worker(self) -> Optional[WorkerInfo]:
        """Get an available worker."""
        async with self.lock:
            for worker in self.workers.values():
                if worker.status == WorkerStatus.AVAILABLE:
                    # Check if worker is still alive (heartbeat within last 30 seconds)
                    if datetime.now() - worker.last_heartbeat < timedelta(seconds=30):
                        return worker
                    else:
                        # Worker might be dead
                        worker.status = WorkerStatus.OFFLINE
                        logger.warning(f"Worker {worker.id} missed heartbeat")
            return None

    async def _assign_task(self, worker: WorkerInfo, subproblem: Subproblem):
        """Assign a subproblem to a worker."""
        async with self.lock:
            worker.status = WorkerStatus.BUSY
            worker.current_task = subproblem.id
            worker.task_start_time = datetime.now()
            subproblem.assigned_worker = worker.id
            subproblem.status = "assigned"
            self.subproblem_to_worker[subproblem.id] = worker.id

        # Send task to worker asynchronously
        asyncio.create_task(self._send_task_to_worker(worker, subproblem))

    async def _send_task_to_worker(self, worker: WorkerInfo, subproblem: Subproblem):
        """Send task to worker and handle response."""
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
                    # Convert JSON to Placement objects
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
                    
                    # Task completed successfully
                    future = self.futures.pop(subproblem.id, None)
                    if future:
                        future.set_result(placements)
                    
                    # Update worker status
                    await self.update_heartbeat(worker.id, WorkerStatus.AVAILABLE, None)
                    logger.info(f"Subproblem {subproblem.id} completed by worker {worker.id}")
                    
                else:
                    raise Exception(f"Worker returned status {resp.status}")
                    
        except asyncio.TimeoutError:
            logger.error(f"Worker {worker.id} timeout for subproblem {subproblem.id}")
            await self._handle_worker_failure(worker, subproblem.id)
        except Exception as e:
            logger.error(f"Worker {worker.id} failed: {e}")
            await self._handle_worker_failure(worker, subproblem.id)

    async def _handle_worker_failure(self, worker: WorkerInfo, subproblem_id: int):
        """Handle worker failure and reassign task."""
        # Mark worker as offline
        await self.unregister_worker(worker.id)
        
        # Reassign the failed subproblem
        await self._reassign_task(subproblem_id)

    async def _reassign_task(self, subproblem_id: int):
        """Reassign a failed subproblem."""
        if subproblem_id in self.futures:
            # Find original subproblem (we need to reconstruct it)
            # For now, we'll need to store subproblems separately
            # This is simplified - in practice you'd have a subproblem store
            logger.info(f"Requeuing subproblem {subproblem_id}")
            # Requeue the subproblem (you'll need to store subproblem objects)
            # await self.pending_queue.put(subproblem)
        elif subproblem_id in self.subproblem_to_worker:
            # Clean up mapping
            del self.subproblem_to_worker[subproblem_id]

    async def _heartbeat_monitor(self):
        """Monitor worker heartbeats and remove dead workers."""
        while self.running:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                current_time = datetime.now()
                async with self.lock:
                    dead_workers = []
                    for worker_id, worker in self.workers.items():
                        if worker.status == WorkerStatus.BUSY:
                            # Check if task has been running too long
                            if worker.task_start_time and \
                               current_time - worker.task_start_time > timedelta(seconds=self.config.task_timeout):
                                logger.warning(f"Worker {worker_id} task timeout, marking as dead")
                                dead_workers.append(worker_id)
                        elif worker.status == WorkerStatus.AVAILABLE:
                            # Check if heartbeat is too old
                            if current_time - worker.last_heartbeat > timedelta(seconds=30):
                                logger.warning(f"Worker {worker_id} missed heartbeat, marking as dead")
                                dead_workers.append(worker_id)
                    
                    for worker_id in dead_workers:
                        await self.unregister_worker(worker_id)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {e}")

    def get_worker_status(self) -> Dict[int, dict]:
        """Get current status of all workers."""
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