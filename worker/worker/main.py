#!/usr/bin/env python3
import sys
import os
from pathlib import Path

import asyncio
import argparse
import logging
from datetime import datetime
from aiohttp import web
import aiohttp

from grid_system_common import Placement, Subproblem, WorkerStatus, DIRECTIONS

logger = logging.getLogger(__name__)

class Worker:
    def __init__(self, master_url: str, worker_host: str, worker_port: int):
        self.master_url = master_url
        self.worker_host = worker_host
        self.worker_port = worker_port
        self.worker_id = None
        self.busy = False
        self.current_task = None
        self.session = None
        self.heartbeat_task = None
        self.running = False

    async def register(self):
        """Register with master."""
        self.session = aiohttp.ClientSession()
        data = {'address': f'http://{self.worker_host}:{self.worker_port}'}
        
        try:
            async with self.session.post(f"{self.master_url}/register", json=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self.worker_id = result['worker_id']
                    logger.info(f"Registered with master, worker_id = {self.worker_id}")
                    return True
                else:
                    logger.error(f"Registration failed: {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return False

    async def start_heartbeat(self):
        """Start sending heartbeats to master."""
        self.running = True
        while self.running:
            try:
                await asyncio.sleep(5)  # Send heartbeat every 5 seconds
                await self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    async def _send_heartbeat(self):
        """Send heartbeat to master."""
        if not self.worker_id:
            return
            
        status = WorkerStatus.BUSY if self.busy else WorkerStatus.AVAILABLE
        data = {
            'worker_id': self.worker_id,
            'status': status.value,
            'current_task': self.current_task
        }
        
        try:
            async with self.session.post(f"{self.master_url}/heartbeat", json=data, timeout=2) as resp:
                if resp.status != 200:
                    logger.warning(f"Heartbeat failed: {resp.status}")
        except asyncio.TimeoutError:
            logger.warning("Heartbeat timeout")
        except Exception as e:
            logger.warning(f"Heartbeat error: {e}")

    async def handle_task(self, request):
        """Process a subproblem and return placements."""
        if self.busy:
            return web.Response(status=503, text="Worker busy")
            
        try:
            data = await request.json()
            sub_id = data['id']
            words = data['words']
            matrix = data['matrix']
            
            self.busy = True
            self.current_task = sub_id
            logger.info(f"Processing task {sub_id} with {len(words)} words")
            
            # Generate placements for each word
            placements = []
            for word in words:
                placements.extend(self.find_placements(matrix, word))
            
            # Convert to JSON-serializable
            result = {
                'placements': [
                    {
                        'word': p.word,
                        'row': p.row,
                        'col': p.col,
                        'dr': p.dr,
                        'dc': p.dc,
                        'cells': p.cells
                    }
                    for p in placements
                ]
            }
            
            logger.info(f"Task {sub_id} completed, found {len(placements)} placements")
            return web.json_response(result)
            
        except Exception as e:
            logger.error(f"Error processing task: {e}")
            return web.Response(status=500, text=str(e))
        finally:
            self.busy = False
            self.current_task = None

    def find_placements(self, matrix, word):
        """Find all placements of word in matrix."""
        placements = []
        h = len(matrix)
        w = len(matrix[0])
        first_char = word[0]
        
        for r in range(h):
            for c in range(w):
                if matrix[r][c] != first_char:
                    continue
                for dr, dc in DIRECTIONS:
                    ok = True
                    cells = []
                    for i, ch in enumerate(word):
                        nr = r + i*dr
                        nc = c + i*dc
                        if nr < 0 or nr >= h or nc < 0 or nc >= w:
                            ok = False
                            break
                        if matrix[nr][nc] != ch:
                            ok = False
                            break
                        cells.append((nr, nc))
                    if ok:
                        placements.append(Placement(word, r, c, dr, dc, cells))
        return placements

    async def handle_status(self, request):
        """Return worker status."""
        return web.json_response({
            'worker_id': self.worker_id,
            'busy': self.busy,
            'current_task': self.current_task
        })

    async def start(self):
        """Start worker's HTTP server."""
        app = web.Application()
        app.router.add_post('/task', self.handle_task)
        app.router.add_get('/status', self.handle_status)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.worker_host, self.worker_port)
        await site.start()
        
        logger.info(f"Worker listening on {self.worker_host}:{self.worker_port}")
        
        # Start heartbeat
        self.heartbeat_task = asyncio.create_task(self.start_heartbeat())
        
        # Keep running
        await asyncio.Event().wait()

    async def stop(self):
        """Stop worker."""
        self.running = False
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.session:
            await self.session.close()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('master_url', help='URL of master node (e.g., http://127.0.0.1:8080)')
    parser.add_argument('--host', default='127.0.0.1', help='Worker host')
    parser.add_argument('--port', type=int, default=5000, help='Worker port')
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    worker = Worker(args.master_url, args.host, args.port)
    
    # Register with master
    if not await worker.register():
        logger.error("Failed to register with master")
        return
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Worker shutting down")
    finally:
        await worker.stop()

if __name__ == "__main__":
    asyncio.run(main())