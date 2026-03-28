import asyncio
import json
import os
import time
from typing import List
import aiohttp
from aiohttp import web
import asyncio
import threading

from grid_system_common import Subproblem, Placement, WorkerStatus
from generator import Generator
from dispatcher import Dispatcher

class Master:
    def __init__(self, config):
        self.config = config
        self.matrix = None
        self.words = None
        self.generator = None
        self.dispatcher = None
        self.subproblems = []
        self.results = {}          # subproblem_id -> list of placements
        self.computation_started = False
        self.computation_done = False
        self.final_placements = []  # selected placements after covering

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
        return matrix

    def load_words(self, path):
        with open(path, 'r') as f:
            self.words = [line.strip() for line in f if line.strip()]
        return self.words

    async def start_computation(self):
        if self.computation_started:
            return
        self.computation_started = True
        self.computation_done = False

        # Create generator and compute placement counts
        self.generator = Generator(self.matrix, self.words, self.config.coefficient)
        # Run counting in thread to avoid blocking event loop
        await asyncio.to_thread(self.generator.compute_placement_counts)
        self.generator.create_subproblems()
        self.subproblems = self.generator.subproblems

        # Start dispatcher
        self.dispatcher = Dispatcher(self.config, self.matrix)
        await self.dispatcher.start()

        # Submit subproblems to dispatcher
        for sub in self.subproblems:
            try:
                placements = await self.dispatcher.submit_subproblem(sub)
                self.results[sub.id] = placements
            except Exception as e:
                print(f"Subproblem {sub.id} failed: {e}")

        # After all subproblems are processed, compute final covering
        all_placements = []
        for placements in self.results.values():
            all_placements.extend(placements)
        self.final_placements = self.compute_covering(all_placements)
        self.computation_done = True

    def compute_covering(self, all_placements: List[Placement]):
        total_cells = len(self.matrix) * len(self.matrix[0])
        covered = set()
        selected = []
        # Greedy selection
        remaining = all_placements[:]
        while len(covered) < total_cells:
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
        return {
            "started": self.computation_started,
            "done": self.computation_done,
            "subproblems_total": len(self.subproblems),
            "subproblems_solved": len(self.results),
            "final_placements_count": len(self.final_placements),
            "covered_cells": len(set(cell for p in self.final_placements for cell in p.cells))
        }

    def get_subproblem_info(self, sub_id):
        if 0 <= sub_id < len(self.subproblems):
            sub = self.subproblems[sub_id]
            solved = sub.id in self.results
            return {
                "id": sub.id,
                "words": sub.words,
                "complexity": sub.complexity,
                "solved": solved,
                "placements": self.results.get(sub.id, [])
            }
        return None


class Console:
    def __init__(self, master):
        self.master = master
        self.running = True
        self.current_menu = "main"

    async def run(self):
        while self.running:
            self.show_menu()
            choice = await asyncio.to_thread(input, "Выберите пункт: ")
            await self.handle_choice(choice)

    def show_menu(self):
        if self.current_menu == "main":
            print("\n=== ГРИД-СИСТЕМА (MASTER) ===")
            print("1. Настройки")
            print("2. Запустить вычисление")
            if self.master.computation_started:
                print("3. Статус (вычисления идут)")
            else:
                print("3. Статус (заблокировано)")
            print("0. Выход")
        elif self.current_menu == "status":
            print("\n=== СТАТУС ВЫЧИСЛЕНИЙ ===")
            status = self.master.get_status()
            print(f"Вычисления начаты: {status['started']}")
            print(f"Вычисления завершены: {status['done']}")
            print(f"Всего подзадач: {status['subproblems_total']}")
            print(f"Решено подзадач: {status['subproblems_solved']}")
            print(f"Выбрано слов в решении: {status['final_placements_count']}")
            print(f"Покрыто клеток: {status['covered_cells']}")
            print("\nПодменю:")
            print("1. Показать решение (если готово)")
            print("2. Показать подзадачи")
            print("3. Статус воркеров")
            print("0. Назад")
        elif self.current_menu == "subproblems":
            # Subproblem pagination logic would go here
            pass
        elif self.current_menu == "workers":
            pass

    async def handle_choice(self, choice):
        if self.current_menu == "main":
            if choice == "1":
                await self.show_settings()
            elif choice == "2":
                if not self.master.computation_started:
                    await self.master.start_computation()
                    print("Вычисления запущены.")
                else:
                    print("Вычисления уже запущены.")
            elif choice == "3":
                if self.master.computation_started:
                    self.current_menu = "status"
                else:
                    print("Пункт недоступен.")
            elif choice == "0":
                self.running = False
        elif self.current_menu == "status":
            if choice == "1":
                if self.master.computation_done:
                    self.show_solution()
                else:
                    print("Решение ещё не готово.")
            elif choice == "2":
                self.current_menu = "subproblems"
                await self.show_subproblems()
            elif choice == "3":
                self.current_menu = "workers"
                await self.show_workers()
            elif choice == "0":
                self.current_menu = "main"
        # Handle other menus similarly...

    async def show_settings(self):
        print("\n=== НАСТРОЙКИ ===")
        print(f"Путь к матрице: {self.master.config.matrix_path}")
        print(f"Путь к словарю: {self.master.config.words_path}")
        print(f"Коэффициент сложности: {self.master.config.coefficient}")
        print(f"Таймаут воркера: {self.master.config.worker_timeout} сек")
        print("1. Изменить коэффициент сложности")
        print("0. Назад")
        choice = await asyncio.to_thread(input, "Выберите: ")
        if choice == "1":
            new_val = await asyncio.to_thread(input, "Новый коэффициент: ")
            try:
                self.master.config.coefficient = int(new_val)
                print("Коэффициент изменён.")
            except ValueError:
                print("Неверное значение.")
        # Other settings can be added similarly

    def show_solution(self):
        print("\n=== ИТОГОВОЕ РЕШЕНИЕ ===")
        print(f"Выбрано слов: {len(self.master.final_placements)}")
        for p in self.master.final_placements:
            print(f"{p.word} ({p.row},{p.col}) dr={p.dr} dc={p.dc}")
        # Show matrix with covered cells (optional)
        # ...

    async def show_subproblems(self):
        # Simple pagination
        page = 0
        while True:
            sub = self.master.get_subproblem_info(page)
            if not sub:
                print("Нет подзадачи с таким номером.")
                break
            print(f"\nПодзадача {sub['id']}")
            print(f"Слова: {', '.join(sub['words'])}")
            print(f"Сложность: {sub['complexity']}")
            print(f"Статус: {'решена' if sub['solved'] else 'не решена'}")
            if sub['solved']:
                print(f"Найдено расстановок: {len(sub['placements'])}")
            print("\n[N] следующая, [P] предыдущая, [Q] выход")
            cmd = await asyncio.to_thread(input, "Команда: ")
            if cmd.lower() == 'n':
                page += 1
            elif cmd.lower() == 'p' and page > 0:
                page -= 1
            elif cmd.lower() == 'q':
                break

    async def show_workers(self):
        print("\n=== ВОРКЕРЫ ===")
        for w in self.master.dispatcher.workers.values():
            print(f"ID {w.id} | Адрес {w.address} | Занят: {w.busy}")
        print("\nНажмите Enter для возврата")
        await asyncio.to_thread(input)


class Config:
    def __init__(self):
        self.matrix_path = "matrix.txt"
        self.words_path = "words.txt"
        self.coefficient = 1000
        self.worker_timeout = 5.0
        self.master_host = "127.0.0.1"
        self.master_port = 8080

    def load(self, path):
        # Load from file if needed
        pass


async def master_http_handler(master):
    app = web.Application()
    app['master'] = master

    async def register(request):
        data = await request.json()
        address = data['address']
        worker_id = await master.dispatcher.register_worker(address)
        return web.json_response({'worker_id': worker_id})

    async def heartbeat(request):
        data = await request.json()
        worker_id = data['worker_id']
        status = WorkerStatus(data['status'])
        current_task = data.get('current_task')
        await master.dispatcher.update_heartbeat(worker_id, status, current_task)
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
    return runner


async def main():
    config = Config()
    # Load matrix and words from command line or interactive
    config.matrix_path = input("Путь к файлу матрицы: ").strip()
    config.words_path = input("Путь к файлу словаря: ").strip()
    config.coefficient = int(input("Коэффициент сложности: ").strip())

    master = Master(config)
    try:
        master.load_matrix(config.matrix_path)
        master.load_words(config.words_path)
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}")
        return

    # Start HTTP server for workers
    http_runner = await master_http_handler(master)

    # Run console
    console = Console(master)
    try:
        await console.run()
    finally:
        # Cleanup
        if master.dispatcher:
            await master.dispatcher.stop()
        await http_runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())