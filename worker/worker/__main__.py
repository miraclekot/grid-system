#!/usr/bin/env python3
# worker.py
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
from aiohttp.client_exceptions import ClientConnectorError, ClientResponseError

from grid_system_common import Placement, Subproblem, WorkerStatus, DIRECTIONS

# Определение корневой директории
PROJECT_ROOT = Path(__file__).parent.parent.parent


class Worker:
    def __init__(self, master_url: str, worker_host: str, worker_port: int, reconnect_attempts: int = 5, reconnect_delay: float = 5.0):
        self.master_url = master_url
        self.worker_host = worker_host
        self.worker_port = worker_port
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.worker_id = None
        self.busy = False
        self.current_task = None
        self.session = None
        self.heartbeat_task = None
        self.registration_task = None
        self.running = True
        self.registered = False
        
        # Настройка логирования
        self._setup_logging()
    
    def _setup_logging(self):
        """Настройка логирования воркера."""
        self.logger = logging.getLogger("grid_system.worker")
        self.logger.setLevel(logging.DEBUG)
        
        # Консольный обработчик
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(console_handler)
    
    async def register_with_retry(self):
        """Регистрация в мастере с повторными попытками."""
        attempt = 0
        while attempt < self.reconnect_attempts:
            attempt += 1
            self.logger.info(f"Registration attempt {attempt}/{self.reconnect_attempts}")
            
            if await self.register():
                self.registered = True
                self.logger.info(f"Successfully registered with master, worker_id = {self.worker_id}")
                return True
            
            if attempt < self.reconnect_attempts:
                self.logger.warning(f"Registration failed, retrying in {self.reconnect_delay} seconds...")
                await asyncio.sleep(self.reconnect_delay)
        
        self.logger.error("Failed to register with master after all attempts")
        return False
    
    async def register(self):
        """Регистрация в мастере."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        
        data = {'address': f'http://{self.worker_host}:{self.worker_port}'}
        
        try:
            async with self.session.post(f"{self.master_url}/register", json=data, timeout=5) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self.worker_id = result['worker_id']
                    return True
                else:
                    self.logger.error(f"Registration failed with status: {resp.status}")
                    return False
        except asyncio.TimeoutError:
            self.logger.error("Registration timeout")
            return False
        except ClientConnectorError as e:
            self.logger.error(f"Cannot connect to master: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Registration error: {e}")
            return False
    
    async def reconnect(self):
        """Попытка переподключения к мастеру."""
        self.logger.warning("Attempting to reconnect to master...")
        self.registered = False
        self.worker_id = None
        
        # Закрываем старую сессию
        if self.session:
            await self.session.close()
            self.session = None
        
        # Пытаемся перерегистрироваться
        if await self.register_with_retry():
            self.logger.info("Reconnected to master successfully")
        else:
            self.logger.error("Failed to reconnect to master")
    
    async def start_heartbeat(self):
        """Запуск отправки heartbeat с обработкой потери соединения."""
        heartbeat_failures = 0
        max_failures = 3
        
        while self.running:
            try:
                await asyncio.sleep(5)
                
                self.logger.info(f"Send heartbeat status...")
                
                if not self.registered:
                    self.logger.debug("Not registered, skipping heartbeat")
                    continue
                
                if await self._send_heartbeat():
                    heartbeat_failures = 0
                else:
                    heartbeat_failures += 1
                    self.logger.warning(f"Heartbeat failed ({heartbeat_failures}/{max_failures})")
                    
                    if heartbeat_failures >= max_failures:
                        self.logger.error("Lost connection to master, attempting to reconnect...")
                        await self.reconnect()
                        heartbeat_failures = 0
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
                heartbeat_failures += 1
                
                if heartbeat_failures >= max_failures:
                    await self.reconnect()
                    heartbeat_failures = 0
                    
        self.logger.info(f"Stop heartbeat status.")
    
    async def _send_heartbeat(self) -> bool:
        """Отправка heartbeat мастеру."""        
        if not self.worker_id or not self.registered:
            return False
        
        status = WorkerStatus.BUSY if self.busy else WorkerStatus.AVAILABLE
        data = {
            'worker_id': self.worker_id,
            'status': status.value,
            'current_task': self.current_task
        }
        
        try:
            async with self.session.post(f"{self.master_url}/heartbeat", json=data, timeout=3) as resp:
                if resp.status == 200:
                    return True
                else:
                    self.logger.warning(f"Heartbeat failed: HTTP {resp.status}")
                    return False
        except asyncio.TimeoutError:
            self.logger.warning("Heartbeat timeout")
            return False
        except ClientConnectorError:
            self.logger.warning("Cannot connect to master for heartbeat")
            return False
        except Exception as e:
            self.logger.warning(f"Heartbeat error: {e}")
            return False
    
    async def handle_task(self, request):
        """Обработка подзадачи."""
        if self.busy:
            return web.Response(status=503, text="Worker busy")
        
        if not self.registered:
            return web.Response(status=503, text="Worker not registered with master")
        
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
            'current_task': self.current_task,
            'registered': self.registered
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
        self.registered = False
        
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self.session:
            await self.session.close()
        
        self.logger.info("Worker stopped")


async def main():
    parser = argparse.ArgumentParser(description='Grid System Worker')
    parser.add_argument('master_url', help='URL of master node (e.g., http://127.0.0.1:8080)')
    parser.add_argument('--host', default='127.0.0.1', help='Worker host')
    parser.add_argument('--port', type=int, default=5000, help='Worker port')
    parser.add_argument('--reconnect-attempts', type=int, default=5, help='Number of reconnection attempts')
    parser.add_argument('--reconnect-delay', type=float, default=5.0, help='Delay between reconnection attempts (seconds)')
    args = parser.parse_args()
    
    print(f"\n{'='*50}")
    print("     ГРИД-СИСТЕМА - WORKER")
    print("="*50)
    print(f"Master URL: {args.master_url}")
    print(f"Worker address: {args.host}:{args.port}")
    print(f"Reconnect attempts: {args.reconnect_attempts}")
    print(f"Reconnect delay: {args.reconnect_delay}s")
    print("="*50)
    
    worker = Worker(
        args.master_url,
        args.host,
        args.port,
        reconnect_attempts=args.reconnect_attempts,
        reconnect_delay=args.reconnect_delay
    )
    
    # Регистрация в мастере с повторными попытками
    if not await worker.register_with_retry():
        print("Failed to register with master. Exiting.")
        return
    
    print(f"Worker registered successfully (ID: {worker.worker_id})")
    print("Press Ctrl+C to stop")
    print("Worker will automatically attempt to reconnect if connection is lost")
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await worker.stop()
        print("Worker stopped.")


if __name__ == "__main__":
    asyncio.run(main())