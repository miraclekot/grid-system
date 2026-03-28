import asyncio
from typing import Optional
from pathlib import Path

from master_node.master import Master


class Console:
    """Консольный интерфейс."""
    
    def __init__(self, master: Master):
        self.master = master
        self.running = True
        self.current_menu = "main"
        self.log_viewing = False
        self.log_lines_per_page = 20
    
    async def run(self):
        """Запуск консольного интерфейса."""
        while self.running:
            self.show_menu()
            choice = await asyncio.to_thread(input, "Выберите пункт: ")
            await self.handle_choice(choice)
    
    def show_menu(self):
        """Отображение главного меню."""
        if self.current_menu == "main":
            print("\n" + "="*60)
            print("     ГРИД-СИСТЕМА (MASTER NODE)")
            print("="*60)
            print("1. Настройки")
            if self.master.computation_started:
                print("2. Вычисления (запущены)")
            else:
                print("2. Запустить вычисление")
            print("3. Статус")
            print("4. Логи")
            print("5. Показать матрицу")
            print("0. Выход")
            print("-"*60)
            
        elif self.current_menu == "status":
            self.show_status_menu()
            
        elif self.current_menu == "logs":
            self.show_logs_menu()
    
    def show_status_menu(self):
        """Отображение меню статуса."""
        status = self.master.get_status()
        print("\n" + "="*60)
        print("          СТАТУС ВЫЧИСЛЕНИЙ")
        print("="*60)
        print(f"Вычисления запущены: {'Да' if status['started'] else 'Нет'}")
        print(f"Вычисления завершены: {'Да' if status['done'] else 'Нет'}")
        print(f"Всего подзадач: {status['subproblems_total']}")
        print(f"Решено подзадач: {status['subproblems_solved']}")
        print(f"Ожидают решения: {status['subproblems_pending']}")
        print(f"Выбрано слов: {status['final_placements_count']}")
        print(f"Всего клеток: {status['total_cells']}")
        print(f"Покрыто клеток: {status['covered_cells']}")
        print(f"Не покрыто клеток: {status['uncovered_cells']}")
        
        # Статистика по воркерам
        workers = status.get('workers', {})
        if workers:
            print("\n--- Воркеры ---")
            for wid, w in workers.items():
                status_icon = {
                    "available": "🟢",
                    "busy": "🟡",
                    "offline": "🔴"
                }.get(w['status'], "⚪")
                print(f"  {status_icon} Воркер {wid}: {w['status']} | {w['address']}")
                if w.get('current_task'):
                    print(f"    Текущая задача: {w['current_task']}")
        
        print("\n" + "-"*60)
        print("Подменю:")
        print("1. Показать решение")
        print("2. Показать подзадачи")
        print("3. Показать воркеров")
        print("4. Показать матрицу (покрытие)")
        print("0. Назад")
        print("-"*60)
    
    def show_logs_menu(self):
        """Отображение меню логов."""
        print("\n" + "="*60)
        print("             ЛОГИ")
        print("="*60)
        print("1. Master log")
        print("2. Generator log")
        print("3. Dispatcher log")
        print("0. Назад")
        print("-"*60)
    
    async def handle_choice(self, choice):
        """Обработка выбора пользователя."""
        if self.current_menu == "main":
            await self.handle_main_menu(choice)
        elif self.current_menu == "status":
            await self.handle_status_menu(choice)
        elif self.current_menu == "logs":
            await self.handle_logs_menu(choice)
        elif self.current_menu == "log_viewer":
            await self.handle_log_viewer(choice)
    
    async def handle_main_menu(self, choice):
        """Обработка главного меню."""
        if choice == "1":
            await self.show_settings()
        elif choice == "2":
            if not self.master.computation_started:
                print("\nЗапуск вычислений...")
                await self.master.start_computation()
                print("Вычисления запущены.")
            else:
                print("Вычисления уже запущены.")
        elif choice == "3":
            if self.master.computation_started:
                self.current_menu = "status"
            else:
                print("Пункт недоступен. Сначала запустите вычисления.")
        elif choice == "4":
            self.current_menu = "logs"
        elif choice == "5":
            self.show_matrix()
        elif choice == "0":
            print("\nВыход...")
            self.running = False
    
    async def handle_status_menu(self, choice):
        """Обработка меню статуса."""
        if choice == "1":
            self.show_solution()
        elif choice == "2":
            await self.show_subproblems()
        elif choice == "3":
            self.show_workers()
        elif choice == "4":
            self.show_covered_matrix()
        elif choice == "0":
            self.current_menu = "main"
    
    async def handle_logs_menu(self, choice):
        """Обработка меню логов."""
        component_map = {
            "1": "master",
            "2": "generator",
            "3": "dispatcher"
        }
        
        if choice in component_map:
            component = component_map[choice]
            await self.view_log(component)
        elif choice == "0":
            self.current_menu = "main"
    
    async def handle_log_viewer(self, choice):
        """Обработка команд в просмотрщике логов."""
        pass
    
    async def show_settings(self):
        """Отображение и изменение настроек."""
        print("\n" + "="*60)
        print("          НАСТРОЙКИ")
        print("="*60)
        print(f"1. Путь к матрице: {self.master.config.matrix_path}")
        print(f"2. Путь к словарю: {self.master.config.words_path}")
        print(f"3. Коэффициент сложности: {self.master.config.coefficient}")
        print(f"4. Таймаут воркера (сек): {self.master.config.worker_timeout}")
        print("0. Назад")
        print("-"*60)
        
        choice = await asyncio.to_thread(input, "Выберите параметр для изменения: ")
        
        if choice == "1":
            new_path = await asyncio.to_thread(input, "Новый путь к матрице: ")
            try:
                self.master.load_matrix(new_path)
                self.master.config.matrix_path = new_path
                print("Матрица обновлена.")
            except Exception as e:
                print(f"Ошибка загрузки матрицы: {e}")
        elif choice == "2":
            new_path = await asyncio.to_thread(input, "Новый путь к словарю: ")
            try:
                self.master.load_words(new_path)
                self.master.config.words_path = new_path
                print("Словарь обновлен.")
            except Exception as e:
                print(f"Ошибка загрузки словаря: {e}")
        elif choice == "3":
            try:
                new_val = int(await asyncio.to_thread(input, "Новый коэффициент: "))
                self.master.config.coefficient = new_val
                print("Коэффициент изменен.")
            except ValueError:
                print("Неверное значение.")
        elif choice == "4":
            try:
                new_val = float(await asyncio.to_thread(input, "Новый таймаут (сек): "))
                self.master.config.worker_timeout = new_val
                print("Таймаут изменен.")
            except ValueError:
                print("Неверное значение.")
    
    async def show_matrix(self):
        """Отображение исходной матрицы."""
        print("\n" + "="*60)
        print("          ИСХОДНАЯ МАТРИЦА")
        print("="*60)
        print(self.master.get_matrix_display())
        await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
    
    async def show_covered_matrix(self):
        """Отображение матрицы с покрытием."""
        if not self.master.final_placements:
            print("\nРешение еще не найдено.")
            return
        
        print("\n" + "="*60)
        print("     МАТРИЦА С ПОКРЫТИЕМ ([X] - покрыто)")
        print("="*60)
        print(self.master.get_covered_matrix_display())
        await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
    
    async def show_solution(self):
        """Отображение итогового решения."""
        print("\n" + "="*60)
        print("       ИТОГОВОЕ РЕШЕНИЕ")
        print("="*60)
        
        if not self.master.final_placements:
            print("Решение не найдено.")
            return
        
        print(f"Выбрано слов: {len(self.master.final_placements)}")
        print("\nРазмещения:")
        
        direction_map = {
            (0, 1): "→ (вправо)",
            (0, -1): "← (влево)",
            (1, 0): "↓ (вниз)",
            (-1, 0): "↑ (вверх)",
            (1, 1): "↘ (вниз-вправо)",
            (1, -1): "↙ (вниз-влево)",
            (-1, 1): "↗ (вверх-вправо)",
            (-1, -1): "↖ (вверх-влево)"
        }
        
        for i, p in enumerate(self.master.final_placements[:30], 1):
            direction = direction_map.get((p.dr, p.dc), f"({p.dr},{p.dc})")
            print(f"  {i:2d}. {p.word} → [{p.row}, {p.col}] {direction}")
        
        if len(self.master.final_placements) > 30:
            print(f"  ... и еще {len(self.master.final_placements) - 30} слов")
        
        await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
    
    async def show_subproblems(self):
        """Показ списка подзадач с пагинацией."""
        page = 0
        page_size = 10
        
        while True:
            sub_ids = sorted(self.master.subproblems.keys())
            total_pages = (len(sub_ids) + page_size - 1) // page_size if sub_ids else 1
            
            print("\n" + "="*70)
            print(f"       ПОДЗАДАЧИ (страница {page+1}/{total_pages})")
            print("="*70)
            
            start = page * page_size
            end = min(start + page_size, len(sub_ids))
            
            for sub_id in sub_ids[start:end]:
                info = self.master.get_subproblem_info(sub_id)
                if info:
                    status_color = "\033[92mрешена\033[0m" if info['solved'] else "\033[93mне решена\033[0m"
                    print(f"\n[{info['id']}] Сложность: {info['complexity']} | Статус: {status_color}")
                    print(f"    Слова: {', '.join(info['words'][:5])}")
                    if len(info['words']) > 5:
                        print(f"    ... и еще {len(info['words']) - 5} слов")
                    if info['solved']:
                        print(f"    Найдено размещений: {info['placements_count']}")
            
            print("\n" + "-"*70)
            print("[N] следующая | [P] предыдущая | [G] перейти к задаче | [Q] выход")
            
            cmd = await asyncio.to_thread(input, "Команда: ")
            
            if cmd.lower() == 'n' and page < total_pages - 1:
                page += 1
            elif cmd.lower() == 'p' and page > 0:
                page -= 1
            elif cmd.lower() == 'g':
                try:
                    sub_id = int(await asyncio.to_thread(input, "Номер задачи: "))
                    info = self.master.get_subproblem_info(sub_id)
                    if info:
                        await self.show_subproblem_detail(sub_id)
                    else:
                        print("Задача не найдена.")
                except ValueError:
                    print("Неверный номер.")
            elif cmd.lower() == 'q':
                break
    
    async def show_subproblem_detail(self, sub_id: int):
        """Показ деталей конкретной подзадачи."""
        info = self.master.get_subproblem_info(sub_id)
        if not info:
            return
        
        print("\n" + "="*60)
        print(f"       ПОДЗАДАЧА {sub_id}")
        print("="*60)
        print(f"Слова: {', '.join(info['words'])}")
        print(f"Сложность: {info['complexity']}")
        print(f"Статус: {'решена' if info['solved'] else 'не решена'}")
        print(f"Создана: {info['created_at']}")
        if info['solved_at']:
            print(f"Решена: {info['solved_at']}")
        if info['assigned_worker']:
            print(f"Воркер: {info['assigned_worker']}")
        
        if info['solved'] and info['placements_count'] > 0:
            print(f"\nНайдено размещений: {info['placements_count']}")
        
        await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
    
    async def show_workers(self):
        """Показ статуса воркеров."""
        status = self.master.get_status()
        workers = status.get('workers', {})
        
        print("\n" + "="*60)
        print("         СТАТУС ВОРКЕРОВ")
        print("="*60)
        
        if not workers:
            print("Нет активных воркеров.")
        else:
            for wid, w in workers.items():
                status_icon = {
                    "available": "🟢",
                    "busy": "🟡",
                    "offline": "🔴"
                }.get(w['status'], "⚪")
                
                print(f"\n{status_icon} Воркер {wid}")
                print(f"   Адрес: {w['address']}")
                print(f"   Статус: {w['status']}")
                if w.get('current_task'):
                    print(f"   Текущая задача: {w['current_task']}")
                if w.get('last_heartbeat'):
                    print(f"   Последний heartbeat: {w['last_heartbeat']}")
        
        await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
    
    async def view_log(self, component: str):
        """Просмотр лога с поддержкой пагинации и автообновления."""
        self.current_menu = "log_viewer"
        offset = 0
        lines_per_page = 20
        watching = False
        last_total_lines = 0
        
        while True:
            lines, total_lines, end_reached = self.master.log_manager.read_log(
                component, lines_per_page, offset
            )
            
            print("\n" + "="*70)
            print(f"Лог: {component}.log (строки {offset+1}-{min(offset+lines_per_page, total_lines)} из {total_lines})")
            print("="*70)
            
            for line in lines:
                print(line.rstrip())
            
            print("-"*70)
            if watching and end_reached:
                print("[A] Автообновление включено - следим за новыми записями...")
            elif watching:
                print("[A] Автообновление включено")
            else:
                print("[A] Включить автообновление (следить за новыми записями)")
            
            print("[N] Следующая страница | [P] Предыдущая | [G] Перейти к строке")
            print("[R] Обновить | [Q] Выход из просмотра")
            print("-"*70)
            
            # Если включено автообновление и достигнут конец файла
            if watching and end_reached:
                if total_lines > last_total_lines:
                    offset = max(0, total_lines - lines_per_page)
                    last_total_lines = total_lines
                    await asyncio.sleep(0.5)
                    continue
                await asyncio.sleep(1)
                continue
            
            cmd = await asyncio.to_thread(input, "Команда: ")
            
            if cmd.lower() == 'n' and not end_reached:
                offset += lines_per_page
            elif cmd.lower() == 'p' and offset > 0:
                offset = max(0, offset - lines_per_page)
            elif cmd.lower() == 'g':
                try:
                    line_num = int(await asyncio.to_thread(input, "Номер строки: "))
                    if 1 <= line_num <= total_lines:
                        offset = max(0, line_num - lines_per_page)
                except ValueError:
                    pass
            elif cmd.lower() == 'r':
                pass
            elif cmd.lower() == 'a':
                watching = not watching
                if watching:
                    last_total_lines = total_lines
                    if end_reached:
                        offset = max(0, total_lines - lines_per_page)
                    print("\nАвтообновление включено.")
            elif cmd.lower() == 'q':
                self.current_menu = "logs"
                break