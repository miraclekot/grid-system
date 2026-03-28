import asyncio
import sys
import argparse
from aiohttp import web
import aiohttp

from grid_system_common import Placement, Subproblem, DIRECTIONS

class Worker:
    def __init__(self, master_url, worker_host, worker_port):
        self.master_url = master_url
        self.worker_host = worker_host
        self.worker_port = worker_port
        self.worker_id = None
        self.busy = False
        self.session = None

    async def register(self):
        """Register with master."""
        self.session = aiohttp.ClientSession()
        data = {'address': f'http://{self.worker_host}:{self.worker_port}'}
        async with self.session.post(f"{self.master_url}/register", json=data) as resp:
            if resp.status == 200:
                result = await resp.json()
                self.worker_id = result['worker_id']
                print(f"Registered with master, worker_id = {self.worker_id}")
            else:
                print(f"Registration failed: {resp.status}")
                sys.exit(1)

    async def handle_task(self, request):
        """Process a subproblem and return placements."""
        if self.busy:
            return web.Response(status=503, text="Worker busy")
        data = await request.json()
        sub_id = data['id']
        words = data['words']
        matrix = data['matrix']

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
        return web.json_response(result)

    def find_placements(self, matrix, word):
        """Find all placements of word in matrix."""
        placements = []
        h = len(matrix)
        w = len(matrix[0])
        first_char = word[0]
        # Precompute letter positions for quick start
        for r in range(h):
            for c in range(w):
                if matrix[r][c] != first_char:
                    continue
                for dr, dc in DIRECTIONS:
                    # Check if word fits
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

    async def start(self):
        """Start worker's HTTP server."""
        app = web.Application()
        app.router.add_post('/task', self.handle_task)
        app.router.add_get('/status', lambda req: web.json_response({'busy': self.busy}))

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.worker_host, self.worker_port)
        await site.start()

        print(f"Worker listening on {self.worker_host}:{self.worker_port}")
        # Keep running
        await asyncio.Event().wait()

    async def stop(self):
        if self.session:
            await self.session.close()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('master_url', help='URL of master node (e.g., http://127.0.0.1:8080)')
    parser.add_argument('--host', default='127.0.0.1', help='Worker host')
    parser.add_argument('--port', type=int, default=5000, help='Worker port')
    args = parser.parse_args()

    worker = Worker(args.master_url, args.host, args.port)
    await worker.register()
    await worker.start()

if __name__ == "__main__":
    asyncio.run(main())