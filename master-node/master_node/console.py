# console.py
import asyncio
import os
import sys
from typing import Optional, List, Tuple
from pathlib import Path

from master_node.master import Master


class Console:
    """Консольный интерфейс с очисткой экрана."""
    
    def __init__(self, master: Master):
        self.master = master
        self.running = True
        self.current_menu = "main"
        self.log_viewing = False
        self.log_lines_per_page = 20
        
        # Символы стрелок для направлений
        self.direction_arrows = {
            (0, 1): "→",
            (0, -1): "←",
            (1, 0): "↓",
            (-1, 0): "↑",
            (1, 1): "↘",
            (1, -1): "↙",
            (-1, 1): "↗",
            (-1, -1): "↖"
        }
    
    def clear_screen(self):
        """Очистка экрана терминала."""
        if os.name == 'nt':
            os.system('cls')
        else:
            os.system('clear')
    
    def print_header(self, title: str):
        """Вывод заголовка."""
        print("="*100)
        print(f"     {title}")
        print("="*100)
    
    def print_footer(self):
        """Вывод подвала с инструкцией."""
        print("-"*100)
        print("Для возврата в главное меню нажмите Ctrl+C")
    
    async def run(self):
        """Запуск консольного интерфейса."""
        try:
            while self.running:
                self.clear_screen()
                self.show_menu()
                choice = await asyncio.to_thread(input, "\nВыберите пункт: ")
                await self.handle_choice(choice)
        except KeyboardInterrupt:
            self.clear_screen()
            print("\nВыход...")
            self.running = False
    
    def show_menu(self):
        """Отображение главного меню."""
        if self.current_menu == "main":
            self.print_header("ГРИД-СИСТЕМА (MASTER NODE)")
            print()
            print("1. Настройки")
            if self.master.computation_started:
                print("2. Вычисления (запущены)")
            else:
                print("2. Запустить вычисление")
            print("3. Статус")
            print("4. Логи")
            print("5. Показать матрицу")
            print("0. Выход")
            self.print_footer()
            
        elif self.current_menu == "status":
            self.show_status_menu()
            
        elif self.current_menu == "logs":
            self.show_logs_menu()
    
    def get_matrix_with_arrows(self) -> str:
        """
        Возвращает матрицу со стрелками, показывающими направление слов.
        Для каждой клетки, входящей в слово, отображается стрелка направления.
        Используется фиксированная ширина для каждой ячейки, чтобы избежать сдвигов.
        """
        if not self.master.matrix or not self.master.final_placements:
            return "Решение еще не найдено."
        
        # Определяем максимальную ширину ячейки (буква + возможная стрелка)
        # Все ячейки будут иметь одинаковую ширину
        cell_width = 2  # Буква + стрелка или пробел
        
        # Создаем матрицу для аннотаций
        rows = len(self.master.matrix)
        cols = len(self.master.matrix[0])
        
        # Инициализируем матрицу с буквами
        annotated = [[""] * cols for _ in range(rows)]
        
        # Заполняем базовыми буквами
        for r in range(rows):
            for c in range(cols):
                annotated[r][c] = self.master.matrix[r][c]
        
        # Добавляем стрелки для начальных позиций слов
        start_positions = {}
        for p in self.master.final_placements:
            start_positions[(p.row, p.col)] = p
        
        # Создаем отформатированные строки
        formatted_rows = []
        for r in range(rows):
            row_cells = []
            for c in range(cols):
                cell_content = annotated[r][c]
                
                # Проверяем, является ли эта клетка началом слова
                if (r, c) in start_positions:
                    p = start_positions[(r, c)]
                    arrow = self.direction_arrows.get((p.dr, p.dc), "•")
                    # Форматируем ячейку: буква + стрелка, выравнивание по левому краю
                    formatted_cell = f"{cell_content}{arrow}".ljust(cell_width)
                else:
                    # Обычная ячейка: буква + пробел
                    formatted_cell = f"{cell_content} ".ljust(cell_width)
                
                row_cells.append(formatted_cell)
            
            # Объединяем ячейки строки
            formatted_rows.append("".join(row_cells))
        
        return "\n".join(formatted_rows)

    def get_used_letters_matrix(self) -> List[str]:
        """
        Возвращает матрицу, где показаны только использованные буквы.
        Неиспользованные клетки отображаются как '.'
        Используется фиксированная ширина для выравнивания.
        """
        if not self.master.matrix or not self.master.final_placements:
            return ["Решение еще не найдено."]
        
        # Собираем все покрытые клетки
        covered_cells = set()
        start_positions = {}
        for p in self.master.final_placements:
            covered_cells.update(p.cells)
            start_positions[(p.row, p.col)] = p
        
        cell_width = 2  # Фиксированная ширина ячейки
        
        # Формируем матрицу
        result = []
        for r, row in enumerate(self.master.matrix):
            row_cells = []
            for c, ch in enumerate(row):
                if (r, c) in covered_cells:
                    # Проверяем, начинается ли здесь слово
                    if (r, c) in start_positions:
                        p = start_positions[(r, c)]
                        arrow = self.direction_arrows.get((p.dr, p.dc), "•")
                        formatted_cell = f"{ch}{arrow}".ljust(cell_width)
                    else:
                        formatted_cell = f"{ch} ".ljust(cell_width)
                else:
                    formatted_cell = ".".ljust(cell_width)
                row_cells.append(formatted_cell)
            
            result.append("".join(row_cells))
        
        return result

    def get_unused_letters_matrix(self) -> List[str]:
        """
        Возвращает матрицу, где показаны только неиспользованные буквы.
        Использованные клетки отображаются как '.'
        Используется фиксированная ширина для выравнивания.
        """
        if not self.master.matrix:
            return ["Матрица не загружена."]
        
        if not self.master.final_placements:
            # Если решения нет, показываем все буквы с фиксированной шириной
            cell_width = 2
            result = []
            for row in self.master.matrix:
                row_cells = [f"{ch} ".ljust(cell_width) for ch in row]
                result.append("".join(row_cells))
            return result
        
        # Собираем все покрытые клетки
        covered_cells = set()
        for p in self.master.final_placements:
            covered_cells.update(p.cells)
        
        cell_width = 2
        
        # Формируем матрицу
        result = []
        for r, row in enumerate(self.master.matrix):
            row_cells = []
            for c, ch in enumerate(row):
                if (r, c) not in covered_cells:
                    formatted_cell = f"{ch} ".ljust(cell_width)
                else:
                    formatted_cell = ".".ljust(cell_width)
                row_cells.append(formatted_cell)
            
            result.append("".join(row_cells))
        
        return result

    def print_three_matrices_horizontal(self, title: str = ""):
        """
        Выводит три матрицы горизонтально в одной строке.
        Все матрицы используют одинаковую ширину ячейки для выравнивания.
        """
        if not self.master.matrix:
            print("Матрица не загружена.")
            return
        
        # Получаем три представления матриц
        original_lines = self.master.get_matrix_display().split('\n')
        used_lines = self.get_used_letters_matrix()
        unused_lines = self.get_unused_letters_matrix()
        
        if not self.master.final_placements:
            used_lines = ["(решение не найдено)"] * len(original_lines)
        
        # Определяем максимальную ширину для каждой матрицы (в символах)
        max_width_original = max(len(line) for line in original_lines) if original_lines else 0
        max_width_used = max(len(line) for line in used_lines) if used_lines else 0
        max_width_unused = max(len(line) for line in unused_lines) if unused_lines else 0
        
        # Заголовки
        print()
        print(f"{'Исходная матрица':^{max_width_original}}   "
            f"{'Использованные буквы':^{max_width_used}}   "
            f"{'Неиспользованные буквы':^{max_width_unused}}")
        print("-"*100)
        
        # Выводим строки матриц горизонтально
        max_rows = max(len(original_lines), len(used_lines), len(unused_lines))
        for i in range(max_rows):
            row_original = original_lines[i] if i < len(original_lines) else " " * max_width_original
            row_used = used_lines[i] if i < len(used_lines) else " " * max_width_used
            row_unused = unused_lines[i] if i < len(unused_lines) else " " * max_width_unused
            
            print(f"{row_original:<{max_width_original}}   "
                f"{row_used:<{max_width_used}}   "
                f"{row_unused:<{max_width_unused}}")
        
        if title:
            print(f"\n{title}")

    def get_matrix_display_with_fixed_width(self) -> str:
        """
        Возвращает исходную матрицу с фиксированной шириной ячеек.
        Используется для выравнивания с другими матрицами.
        """
        if not self.master.matrix:
            return ""
        
        cell_width = 2
        result = []
        for row in self.master.matrix:
            row_cells = [f"{ch} ".ljust(cell_width) for ch in row]
            result.append("".join(row_cells))
        
        return "\n".join(result)

    def get_covered_matrix_display_with_fixed_width(self) -> str:
        """
        Возвращает матрицу с покрытием, используя фиксированную ширину ячеек.
        """
        if not self.master.matrix or not self.master.final_placements:
            return "Решение еще не найдено."
        
        # Собираем все покрытые клетки
        covered_cells = set()
        start_positions = {}
        for p in self.master.final_placements:
            covered_cells.update(p.cells)
            start_positions[(p.row, p.col)] = p
        
        cell_width = 2
        result = []
        for r, row in enumerate(self.master.matrix):
            row_cells = []
            for c, ch in enumerate(row):
                if (r, c) in covered_cells:
                    if (r, c) in start_positions:
                        p = start_positions[(r, c)]
                        arrow = self.direction_arrows.get((p.dr, p.dc), "•")
                        formatted_cell = f"{ch}{arrow}".ljust(cell_width)
                    else:
                        formatted_cell = f"{ch} ".ljust(cell_width)
                else:
                    formatted_cell = f"{ch} ".ljust(cell_width)
                row_cells.append(formatted_cell)
            
            result.append("".join(row_cells))
        
        return "\n".join(result)
    
    def show_status_menu(self):
        """Отображение меню статуса."""
        self.clear_screen()
        self.print_header("СТАТУС ВЫЧИСЛЕНИЙ")
        
        status = self.master.get_status()
        print()
        print(f"Вычисления запущены: {'Да' if status['started'] else 'Нет'}")
        print(f"Вычисления завершены: {'Да' if status['done'] else 'Нет'}")
        print(f"Всего подзадач: {status['subproblems_total']}")
        # print(f"Решено подзадач: {status['subproblems_solved']}")
        # print(f"Ожидают решения: {status['subproblems_pending']}")
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
        
        # Три версии матрицы горизонтально
        if self.master.matrix:
            print("\n" + "="*100)
            print("МАТРИЦЫ БУКВ")
            print("="*100)
            self.print_three_matrices_horizontal()
        
        print("\n" + "-"*100)
        print("1. Показать решение")
        print("2. Показать подзадачи")
        print("3. Показать воркеров")
        print("4. Показать матрицу с направлением слов")
        print("5. Обновить статус")
        print("0. Назад")
        print("-"*100)
    
    def show_logs_menu(self):
        """Отображение меню логов."""
        self.print_header("ЛОГИ")
        print()
        print("1. Master log")
        print("2. Generator log")
        print("3. Dispatcher log")
        print("0. Назад")
        self.print_footer()
    
    async def handle_choice(self, choice):
        """Обработка выбора пользователя."""
        try:
            if self.current_menu == "main":
                await self.handle_main_menu(choice)
            elif self.current_menu == "status":
                await self.handle_status_menu(choice)
            elif self.current_menu == "logs":
                await self.handle_logs_menu(choice)
            elif self.current_menu == "log_viewer":
                await self.handle_log_viewer(choice)
        except KeyboardInterrupt:
            self.current_menu = "main"
            await asyncio.sleep(0.5)
    
    async def handle_main_menu(self, choice):
        """Обработка главного меню."""
        if choice == "1":
            await self.show_settings()
        elif choice == "2":
            if not self.master.computation_started:
                self.clear_screen()
                print(f"\nЗапуск вычислений (количество подзадач: {self.master.get_status()['subproblems_total']})...")
                await self.master.start_computation()
                print("Вычисления запущены.")
                await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
            else:
                self.clear_screen()
                print("Вычисления уже запущены.")
                await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
        elif choice == "3":
            self.current_menu = "status"
        elif choice == "4":
            self.current_menu = "logs"
        elif choice == "5":
            await self.show_matrix()
        elif choice == "0" or choice.lower() == "q":
            self.clear_screen()
            print("\nВыход...")
            self.running = False
    
    async def handle_status_menu(self, choice):
        """Обработка меню статуса."""
        if choice == "1":
            await self.show_solution()
        elif choice == "2":
            await self.show_subproblems()
        elif choice == "3":
            await self.show_workers()
        elif choice == "4":
            await self.show_matrix_with_directions()
        elif choice == "5" or choice.lower() == "r":
            # Обновление статуса - просто остаемся в том же меню
            pass
        elif choice == "0" or choice.lower() == "q":
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
        elif choice == "0" or choice.lower() == "q":
            self.current_menu = "main"
    
    async def handle_log_viewer(self, choice):
        """Обработка команд в просмотрщике логов."""
        pass
    
    async def show_settings(self):
        """Отображение и изменение настроек."""
        while True:
            self.clear_screen()
            self.print_header("НАСТРОЙКИ")
            print()
            print(f"1. Путь к матрице: {self.master.config.matrix_path}")
            print(f"2. Путь к словарю: {self.master.config.words_path}")
            print(f"3. Коэффициент сложности: {self.master.config.coefficient}")
            print(f"4. Таймаут воркера (сек): {self.master.config.worker_timeout}")
            print("0. Назад")
            print("-"*70)
            
            choice = await asyncio.to_thread(input, "Выберите параметр для изменения: ")
            
            if choice == "1":
                new_path = await asyncio.to_thread(input, "Новый путь к матрице: ")
                try:
                    self.master.load_matrix(new_path)
                    self.master.config.matrix_path = new_path
                    self.clear_screen()
                    print("Матрица обновлена.")
                    await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
                except Exception as e:
                    self.clear_screen()
                    print(f"Ошибка загрузки матрицы: {e}")
                    await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
            elif choice == "2":
                new_path = await asyncio.to_thread(input, "Новый путь к словарю: ")
                try:
                    self.master.load_words(new_path)
                    self.master.config.words_path = new_path
                    self.clear_screen()
                    print("Словарь обновлен.")
                    await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
                except Exception as e:
                    self.clear_screen()
                    print(f"Ошибка загрузки словаря: {e}")
                    await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
            elif choice == "3":
                try:
                    new_val = int(await asyncio.to_thread(input, "Новый коэффициент: "))
                    self.master.config.coefficient = new_val
                    self.clear_screen()
                    print("Коэффициент изменен.")
                    await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
                except ValueError:
                    self.clear_screen()
                    print("Неверное значение.")
                    await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
            elif choice == "4":
                try:
                    new_val = float(await asyncio.to_thread(input, "Новый таймаут (сек): "))
                    self.master.config.worker_timeout = new_val
                    self.clear_screen()
                    print("Таймаут изменен.")
                    await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
                except ValueError:
                    self.clear_screen()
                    print("Неверное значение.")
                    await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
            elif choice == "0" or choice.lower() == "q":
                break
    
    async def show_matrix(self):
        """Отображение исходной матрицы."""
        self.clear_screen()
        self.print_header("ИСХОДНАЯ МАТРИЦА")
        print()
        print(self.master.get_matrix_display())
        print()
        await asyncio.to_thread(input, "Нажмите Enter для продолжения...")
    
    async def show_matrix_with_directions(self):
        """Отображение матрицы со стрелками направления слов."""
        if not self.master.final_placements:
            self.clear_screen()
            print("\nРешение еще не найдено.")
            await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
            return
        
        self.clear_screen()
        self.print_header("МАТРИЦА СО СТРЕЛКАМИ НАПРАВЛЕНИЙ")
        print("\n(Стрелки показывают направление чтения слова)")
        print()
        print(self.get_matrix_with_arrows())
        print("\nУсловные обозначения:")
        for direction, arrow in self.direction_arrows.items():
            dir_name = {
                (0, 1): "вправо", (0, -1): "влево",
                (1, 0): "вниз", (-1, 0): "вверх",
                (1, 1): "вниз-вправо", (1, -1): "вниз-влево",
                (-1, 1): "вверх-вправо", (-1, -1): "вверх-влево"
            }.get(direction, "неизвестно")
            print(f"  {arrow} - {dir_name}")
        print()
        await asyncio.to_thread(input, "Нажмите Enter для продолжения...")
    
    async def show_solution(self):
        """Отображение итогового решения."""
        
        self.clear_screen()
        
        if not self.master.final_placements:
            self.clear_screen()
            print("\nРешение не найдено.")
            await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
            return
        
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
        
        # Постраничный вывод решения
        page = 0
        items_per_page = 15
        total_items = len(self.master.final_placements)
        total_pages = (total_items + items_per_page - 1) // items_per_page if total_items > 0 else 1
        
        while True:
            self.clear_screen()
            self.print_header(f"ИТОГОВОЕ РЕШЕНИЕ (страница {page+1}/{total_pages})")
            print(f"\nВыбрано слов: {total_items}")
            print("\nРазмещения:")
            print("-"*100)
            
            start = page * items_per_page
            end = min(start + items_per_page, total_items)
            
            for i, p in enumerate(self.master.final_placements[start:end], start + 1):
                direction = direction_map.get((p.dr, p.dc), f"({p.dr},{p.dc})")
                print(f"  {i:3d}. {p.word} → [{p.row}, {p.col}] {direction}")
            
            # Показываем три версии матрицы горизонтально
            print("\n" + "="*100)
            print("МАТРИЦЫ БУКВ")
            print("="*100)
            self.print_three_matrices_horizontal()
            
            print("-"*100)
            print("[N] следующая | [P] предыдущая | [D] матрица со стрелками | [Q] выход")
            
            cmd = await asyncio.to_thread(input, "\nКоманда: ")
            
            if cmd.lower() == 'n' and page < total_pages - 1:
                page += 1
            elif cmd.lower() == 'p' and page > 0:
                page -= 1
            elif cmd.lower() == 'd':
                await self.show_matrix_with_directions()
            elif cmd.lower() == 'q':
                break
    
    async def show_subproblems(self):
        """Показ списка подзадач с пагинацией."""
        page = 0
        page_size = 10
        
        while True:
            sub_ids = sorted(self.master.subproblems.keys())
            total_pages = (len(sub_ids) + page_size - 1) // page_size if sub_ids else 1
            
            self.clear_screen()
            self.print_header(f"ПОДЗАДАЧИ (страница {page+1}/{total_pages})")
            
            if not sub_ids:
                print("\nНет подзадач.")
                await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
                break
            
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
            
            print("\n" + "-"*100)
            print("[N] следующая | [P] предыдущая | [G] перейти к задаче | [D] детали | [R] обновить | [Q] выход")
            
            cmd = await asyncio.to_thread(input, "Команда: ")
            
            if cmd.lower() == 'n' and page < total_pages - 1:
                page += 1
            elif cmd.lower() == 'p' and page > 0:
                page -= 1
            elif cmd.lower() == 'r':
                continue
            elif cmd.lower() == 'g':
                try:
                    sub_id = int(await asyncio.to_thread(input, "Номер задачи: "))
                    info = self.master.get_subproblem_info(sub_id)
                    if info:
                        await self.show_subproblem_detail(sub_id)
                    else:
                        self.clear_screen()
                        print("Задача не найдена.")
                        await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
                except ValueError:
                    self.clear_screen()
                    print("Неверный номер.")
                    await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
            elif cmd.lower() == 'd':
                try:
                    sub_id = int(await asyncio.to_thread(input, "Номер задачи: "))
                    info = self.master.get_subproblem_info(sub_id)
                    if info:
                        await self.show_subproblem_detail(sub_id)
                    else:
                        self.clear_screen()
                        print("Задача не найдена.")
                        await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
                except ValueError:
                    self.clear_screen()
                    print("Неверный номер.")
                    await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
            elif cmd.lower() == 'q':
                break
    
    async def show_subproblem_detail(self, sub_id: int):
        """Показ деталей конкретной подзадачи."""
        info = self.master.get_subproblem_info(sub_id)
        if not info:
            return
        
        self.clear_screen()
        self.print_header(f"ПОДЗАДАЧА {sub_id}")
        
        print(f"\nСлова: {', '.join(info['words'])}")
        print(f"Сложность: {info['complexity']}")
        print(f"Статус: {'решена' if info['solved'] else 'не решена'}")
        print(f"Создана: {info['created_at']}")
        if info['solved_at']:
            print(f"Решена: {info['solved_at']}")
        if info['assigned_worker']:
            print(f"Воркер: {info['assigned_worker']}")
        
        if info['solved'] and info['placements_count'] > 0:
            print(f"\nНайдено размещений: {info['placements_count']}")
            
            # Показываем первые 10 размещений
            placements = self.master.results.get(sub_id, [])
            if placements:
                print("\nПримеры размещений (первые 10):")
                for i, p in enumerate(placements[:10], 1):
                    arrow = self.direction_arrows.get((p.dr, p.dc), "?")
                    print(f"  {i}. {p.word} [{p.row},{p.col}] {arrow}")
                if len(placements) > 10:
                    print(f"  ... и еще {len(placements) - 10} размещений")
        
        await asyncio.to_thread(input, "\nНажмите Enter для продолжения...")
    
    async def show_workers(self):
        """Показ статуса воркеров."""
        self.clear_screen()
        self.print_header("СТАТУС ВОРКЕРОВ")
        
        status = self.master.get_status()
        workers = status.get('workers', {})
        
        if not workers:
            print("\nНет активных воркеров.")
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
        
        print()
        await asyncio.to_thread(input, "Нажмите Enter для продолжения...")
    
    async def view_log(self, component: str):
        """Просмотр лога с поддержкой пагинации."""
        offset = 0
        lines_per_page = 20
        
        while True:
            lines, total_lines, end_reached = self.master.log_manager.read_log(
                component, lines_per_page, offset
            )
            
            self.clear_screen()
            print("="*100)
            print(f"Лог: {component}.log (строки {offset+1}-{min(offset+lines_per_page, total_lines)} из {total_lines})")
            print("="*100)
            
            if not lines:
                print("\n(лог пуст)")
            else:
                for line in lines:
                    print(line.rstrip())
            
            print("-"*100)
            print("[N] Следующая страница | [P] Предыдущая | [G] Перейти к строке")
            print("[R] Обновить | [Q] Выход из просмотра")
            print("-"*100)
            
            cmd = await asyncio.to_thread(input, "\nКоманда: ")
            
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
            elif cmd.lower() == 'q':
                break