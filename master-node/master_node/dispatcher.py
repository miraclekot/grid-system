import asyncio
import aiohttp
from grid_system_common import Subproblem, WorkerInfo, Placement

class Dispatcher:
    def __init__(self, config, matrix):
        self.config = config
        self.matrix = matrix
        self.workers = {}          # id -> WorkerInfo
        self.next_worker_id = 0
        self.pending_queue = asyncio.Queue()
        self.futures = {}          # subproblem_id -> Future
        self.worker_task = None
        self.session = None
        self.running = False

    async def start(self):
        self.session = aiohttp.ClientSession()
        self.running = True
        self.worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self):
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
        if self.session:
            await self.session.close()

    async def register_worker(self, address):
        worker_id = self.next_worker_id
        self.next_worker_id += 1
        self.workers[worker_id] = WorkerInfo(id=worker_id, address=address, busy=False)
        return worker_id

    async def submit_subproblem(self, subproblem):
        future = asyncio.get_event_loop().create_future()
        self.futures[subproblem.id] = future
        await self.pending_queue.put(subproblem)
        return await future

    async def _worker_loop(self):
        while self.running:
            try:
                subproblem = await self.pending_queue.get()
                free_worker = None
                for w in self.workers.values():
                    if not w.busy:
                        free_worker = w
                        break
                if free_worker is None:
                    # No free worker, wait and retry later
                    await self.pending_queue.put(subproblem)
                    await asyncio.sleep(self.config.worker_timeout)
                    continue

                free_worker.busy = True
                try:
                    result = await self._send_task(free_worker, subproblem)
                    future = self.futures.pop(subproblem.id, None)
                    if future:
                        future.set_result(result)
                except Exception as e:
                    # Worker failed, re‑queue the subproblem and optionally mark worker as dead
                    await self.pending_queue.put(subproblem)
                finally:
                    free_worker.busy = False
            except asyncio.CancelledError:
                break

    async def _send_task(self, worker, subproblem):
        url = f"{worker.address}/task"
        payload = {
            "id": subproblem.id,
            "words": subproblem.words,
            "matrix": self.matrix
        }
        async with self.session.post(url, json=payload) as resp:
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
                return placements
            else:
                raise Exception(f"Worker error: {resp.status}")