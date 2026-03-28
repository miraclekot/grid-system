import argparse
from pathlib import Path
import random
from typing import List

from master_node.generator import SubTask, TaskGenerator
from worker.worker import worker



# SUBTASK_COMPEXITY = 10 ** 7
SUBTASK_COMPEXITY = 10 ** 4

def print_coverage(coverage_matrix: List[List[str]]):
    """
    Красиво выводит матрицу покрытия в консоль.
    """
    print("\n" + "=" * (len(coverage_matrix[0]) * 3))
    for row in coverage_matrix:
        print(" ".join(f"{cell:^2}" for cell in row))
    print("=" * (len(coverage_matrix[0]) * 3) + "\n")

def _handler(subtask: SubTask):
    """
    Обработчик подзадачи.
    """
    print(f"Обработка подзадачи {subtask.task_id}:")
    print(f"  Слов: {len(subtask.words)}")
    print(f"  Сложность: {subtask.metadata['complexity']:.0f}")
    # print(f"  Словарь: {subtask.words}")
    print()
    
    result = worker(subtask)

    # Выводим результат
    print("Исходная матрица:")
    for row in subtask.matrix:
        print(" ".join(row))

    print("\nПокрытые клетки (буквы, '.' - непокрытые):")
    print_coverage(result["coverage_matrix"])

    print(f"Всего покрыто клеток: {result['covered_cells_count']} из {len(subtask.matrix) * len(subtask.matrix[0])}")

    print("\nНайденные размещения:")
    for p in result["placements"]:
        positions_str = ", ".join([f"({x},{y})" for x, y in p["positions"]])
        print(f"  {p['word']} → {positions_str} ({p['direction']})")
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("matrix_filepath", type=str, help="Адрес файла с матрицей букв, разделенными пробелами и переносами строк.")
    parser.add_argument("dict_filepath", type=str, help="Адрес файла со словарем, одно слова - одна строка.")
    parser.add_argument("--shuffle", action="store_true", help="Включить сортировку словаря")

    args = parser.parse_args()

    if not Path(args.matrix_filepath).exists():
        raise Exception(f"matrix file is not exist: {args.matrix_filepath}")

    if not Path(args.dict_filepath).exists():
        raise Exception(f"dictionaire file is not exist: {args.dict_filepath}")
    
    # парсинг матрицы
    matrix = []
    with open(args.matrix_filepath) as f:
        lines = f.readlines()
        
        for l in lines:
            l = l.removesuffix("\n")
            
            row = []
            for sym in l:
                if sym == " ":
                    continue
                row.append(sym)
                
            matrix.append(row)
            
    print(f"[DEBUG] matrix: {matrix}")
    
    # парсинг словаря
    words_list = []
    with open(args.dict_filepath) as f:
        lines = f.readlines()
        
        for l in lines:
            word = l.removesuffix("\n")
            # Проверяем, что слово состоит только из букв
            if word.isalpha():
                words_list.append(word)
            
    if args.shuffle:
        random.shuffle(words_list)

    # print(f"[DEBUG] words_list: {words_list}")
    
    # Создаём генератор
    generator = TaskGenerator(matrix, words_list)
    
    # Генерируем подзадачи
    subtasks = generator.generate_subtasks(
        target_complexity=SUBTASK_COMPEXITY,            # Целевая сложность одной подзадачи
        handler=_handler                                # Обработчик для каждой подзадачи
    )
    