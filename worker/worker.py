from typing import List, Tuple, Dict, Any, Set
from collections import defaultdict
import random
import copy

def find_word_occurrences(matrix: List[List[str]], word: str) -> List[Tuple[List[Tuple[int, int]], str]]:
    """
    Находит все вхождения слова в матрице по всем 8 направлениям.
    Возвращает список: (список координат клеток, направление).
    """
    H = len(matrix)
    W = len(matrix[0]) if H > 0 else 0
    word_len = len(word)
    occurrences = []

    # Направления: (dx, dy, name)
    directions = [
        (1, 0, "right"), (-1, 0, "left"),
        (0, 1, "down"), (0, -1, "up"),
        (1, 1, "down-right"), (-1, -1, "up-left"),
        (1, -1, "up-right"), (-1, 1, "down-left")
    ]

    for y in range(H):
        for x in range(W):
            for dx, dy, dir_name in directions:
                # Проверяем, помещается ли слово
                end_x = x + (word_len - 1) * dx
                end_y = y + (word_len - 1) * dy
                if not (0 <= end_x < W and 0 <= end_y < H):
                    continue
                # Проверяем соответствие букв
                match = True
                positions = []
                for i in range(word_len):
                    px = x + i * dx
                    py = y + i * dy
                    if matrix[py][px] != word[i]:
                        match = False
                        break
                    positions.append((px, py))
                if match:
                    occurrences.append((positions, dir_name))
    return occurrences


def random_order_greedy(word_occurrences: Dict[str, List[Tuple[List[Tuple[int, int]], str]]], attempts: int = 10) -> Tuple[List[Tuple[str, Tuple[List[Tuple[int, int]], str]]], Set[Tuple[int, int]]]:
    """
    Жадный алгоритм с разными порядками слов (для улучшения результата).
    """
    best_chosen = []
    best_covered = set()
    words = list(word_occurrences.keys())

    for _ in range(attempts):
        # Перемешиваем слова
        shuffled_words = words.copy()
        random.shuffle(shuffled_words)

        chosen = []
        covered = set()
        for word in shuffled_words:
            occ_list = word_occurrences[word]
            best_gain = 0
            best_occ = None
            for occ in occ_list:
                gain = len([p for p in occ[0] if p not in covered])
                if gain > best_gain:
                    best_gain = gain
                    best_occ = occ
            if best_gain > 0:
                chosen.append((word, best_occ))
                covered.update(best_occ[0])
        if len(covered) > len(best_covered):
            best_covered = covered
            best_chosen = chosen

    return best_chosen, best_covered


def worker(subtask) -> Dict[str, Any]:
    """
    Воркер, решающий подзадачу.
    subtask: объект с полями:
        - matrix: List[List[str]] (полная таблица)
        - words: List[str] (слова для данной подзадачи)
    Возвращает:
        dict с ключами:
        - coverage_matrix: List[List[str]] (использованные буквы или '.' для непокрытых)
        - coverage_binary: List[List[int]] (0/1 для быстрой обработки)
        - placements: List[dict] информация для визуализации:
            * word: str
            * positions: List[Tuple[int, int]]
            * direction: str
        - covered_cells_count: int
    """
    matrix = subtask.matrix
    words = subtask.words

    # Шаг 1: найти все вхождения всех слов в матрице
    word_occurrences = {}
    for w in words:
        occ = find_word_occurrences(matrix, w)
        if occ:
            word_occurrences[w] = occ

    H = len(matrix)
    W = len(matrix[0]) if H else 0

    if not word_occurrences:
        # Нет ни одного вхождения – возвращаем пустую матрицу
        coverage_matrix = [['.' for _ in range(W)] for _ in range(H)]
        return {
            "coverage_matrix": coverage_matrix,
            "coverage_binary": [[0] * W for _ in range(H)],
            "placements": [],
            "covered_cells_count": 0
        }

    # Шаг 2: применить жадный алгоритм
    chosen_placements, covered_cells = random_order_greedy(word_occurrences, attempts=10)

    # Шаг 3: построить матрицу покрытия с буквами
    coverage_matrix = [['.' for _ in range(W)] for _ in range(H)]
    coverage_binary = [[0] * W for _ in range(H)]

    for (x, y) in covered_cells:
        coverage_matrix[y][x] = matrix[y][x]
        coverage_binary[y][x] = 1

    # Шаг 4: подготовить информацию о размещениях для GUI
    placements_info = []
    for word, (positions, direction) in chosen_placements:
        placements_info.append({
            "word": word,
            "positions": positions,
            "direction": direction
        })

    return {
        "coverage_matrix": coverage_matrix,
        "coverage_binary": coverage_binary,
        "placements": placements_info,
        "covered_cells_count": len(covered_cells)
    }

