#!/usr/bin/env python3
import sys
import os
from pathlib import Path
import asyncio
import argparse
import logging
import logging.handlers
from datetime import datetime
from aiohttp import web
import aiohttp

from grid_system_common import Placement, Subproblem, WorkerStatus, DIRECTIONS

# Определение корневой директории
PROJECT_ROOT = Path(__file__).parent.parent.parent

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
        
        # Настройка логирования
        self._setup_logging()
    
    def _setup_logging(self):
        """Настройка логирования воркера."""
        self.logger = logging.getLogger("grid_system.worker")
        self.logger.setLevel(logging.DEBUG)
        
        # Консольный обработчик
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(console_handler)
    
    async def register(self):
        """Регистрация в мастере."""
        self.session = aiohttp.ClientSession()
        data = {'address': f'http://{self.worker_host}:{self.worker_port}'}
        
        try:
            async with self.session.post(f"{self.master_url}/register", json=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self.worker_id = result['worker_id']
                    self.logger.info(f"Registered with master, worker_id = {self.worker_id}")
                    return True
                else:
                    self.logger.error(f"Registration failed: {resp.status}")
                    return False
        except Exception as e:
            self.logger.error(f"Registration error: {e}")
            return False
    
    async def start_heartbeat(self):
        """Запуск отправки heartbeat."""
        self.running = True
        while self.running:
            try:
                await asyncio.sleep(5)
                await self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
    
    async def _send_heartbeat(self):
        """Отправка heartbeat мастеру."""
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
                    self.logger.warning(f"Heartbeat failed: {resp.status}")
        except asyncio.TimeoutError:
            self.logger.warning("Heartbeat timeout")
        except Exception as e:
            self.logger.warning(f"Heartbeat error: {e}")
    
    async def handle_task(self, request):
        """Обработка подзадачи."""
        if self.busy:
            return web.Response(status=503, text="Worker busy")
        
        try:
            data = await request.json()
            sub_id = data['id']
            words = data['words']
            matrix = data['matrix']
            
            self.busy = True
            self.current_task = sub_id
            self.logger.info(f"Processing task {sub_id} with {len(words)} words")
            
            start_time = datetime.now()
            
            # Генерация размещений для каждого слова
            placements = []
            for word in words:
                word_placements = self.find_placements(matrix, word)
                placements.extend(word_placements)
                self.logger.debug(f"Word '{word}': found {len(word_placements)} placements")
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Преобразование в JSON-сериализуемый формат
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
            
            self.logger.info(f"Task {sub_id} completed in {elapsed:.2f}s, found {len(placements)} placements")
            return web.json_response(result)
            
        except Exception as e:
            self.logger.error(f"Error processing task: {e}", exc_info=True)
            return web.Response(status=500, text=str(e))
        finally:
            self.busy = False
            self.current_task = None
    
    def find_placements(self, matrix, word):
        """Поиск всех размещений слова в матрице."""
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
                        nr = r + i * dr
                        nc = c + i * dc
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
        """Возврат статуса воркера."""
        return web.json_response({
            'worker_id': self.worker_id,
            'busy': self.busy,
            'current_task': self.current_task
        })
    
    async def start(self):
        """Запуск HTTP сервера воркера."""
        app = web.Application()
        app.router.add_post('/task', self.handle_task)
        app.router.add_get('/status', self.handle_status)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.worker_host, self.worker_port)
        await site.start()
        
        self.logger.info(f"Worker listening on {self.worker_host}:{self.worker_port}")
        
        # Запуск heartbeat
        self.heartbeat_task = asyncio.create_task(self.start_heartbeat())
        
        # Ожидание завершения
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            pass
    
    async def stop(self):
        """Остановка воркера."""
        self.logger.info("Stopping worker...")
        self.running = False
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.session:
            await self.session.close()

async def main():
    parser = argparse.ArgumentParser(description='Grid System Worker')
    parser.add_argument('master_url', help='URL of master node (e.g., http://127.0.0.1:8080)')
    parser.add_argument('--host', default='127.0.0.1', help='Worker host')
    parser.add_argument('--port', type=int, default=5000, help='Worker port')
    args = parser.parse_args()
    
    print(f"\n{'='*50}")
    print("     ГРИД-СИСТЕМА - WORKER")
    print("="*50)
    print(f"Master URL: {args.master_url}")
    print(f"Worker address: {args.host}:{args.port}")
    print("="*50)
    
    worker = Worker(args.master_url, args.host, args.port)
    
    # Регистрация в мастере
    if not await worker.register():
        print("Failed to register with master. Exiting.")
        return
    
    print(f"Worker registered successfully (ID: {worker.worker_id})")
    print("Press Ctrl+C to stop")
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await worker.stop()
        print("Worker stopped.")

if __name__ == "__main__":
    asyncio.run(main())