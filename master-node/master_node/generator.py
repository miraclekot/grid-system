# master-node/master_node/generator.py
from pathlib import Path
import logging
from grid_system_common import Subproblem

class Generator:
    """Потоковый генератор подзадач из файла слов."""
    
    def __init__(self, matrix, words_file_path: Path, coefficient: float, log_manager=None):
        self.matrix = matrix
        self.words_file = words_file_path
        self.coefficient = coefficient
        self.matrix_h = len(matrix)
        self.matrix_w = len(matrix[0])
        self.logger = log_manager.get_logger("generator") if log_manager else logging.getLogger("generator")
        self.subproblems_count = 0

    def estimate_word_complexity(self, word: str) -> float:
        """Оценка количества возможных размещений слова в матрице."""
        L = len(word)
        total = 0.0
        w, h = self.matrix_w, self.matrix_h

        # горизонтально
        if L <= w:
            total += 2.0 * (w - L + 1) * h
        # вертикально
        if L <= h:
            total += 2.0 * w * (h - L + 1)
        # диагонально
        if L <= w and L <= h:
            total += 4.0 * (w - L + 1) * (h - L + 1)
        return total

    def create_subproblems(self, storage):
        """
        Создаёт подзадачи, читая слова из файла построчно, и сохраняет их в storage.
        Возвращает количество созданных подзадач.
        """
        self.logger.info(f"Creating subproblems from {self.words_file} with coefficient {self.coefficient}")

        sub_id = 0
        current_words = []
        current_complexity = 0.0

        with open(self.words_file, 'r', encoding='utf-8') as f:
            for line in f:
                word = line.strip()
                if not word:
                    continue

                complexity = self.estimate_word_complexity(word)
                if complexity == 0:
                    self.logger.debug(f"Word '{word}' has no placements, skipping")
                    continue

                # Слово слишком сложное – отдельная подзадача
                if complexity > self.coefficient:
                    # Сначала сохраняем накопленную группу, если есть
                    if current_words:
                        sub = Subproblem(sub_id, current_words, current_complexity)
                        storage.save_subproblem(sub)
                        sub_id += 1
                        current_words = []
                        current_complexity = 0

                    # Сохраняем одно слово как подзадачу
                    sub = Subproblem(sub_id, [word], complexity)
                    storage.save_subproblem(sub)
                    sub_id += 1
                    self.logger.debug(f"Single-word subproblem {sub_id-1}: {word} (complexity: {complexity})")
                    continue

                # Группируем
                if current_complexity + complexity <= self.coefficient:
                    current_words.append(word)
                    current_complexity += complexity
                else:
                    # Сохраняем текущую группу
                    if current_words:
                        sub = Subproblem(sub_id, current_words, current_complexity)
                        storage.save_subproblem(sub)
                        sub_id += 1
                        self.logger.debug(f"Subproblem {sub_id-1}: {len(current_words)} words, complexity: {current_complexity}")
                    # Начинаем новую группу с текущего слова
                    current_words = [word]
                    current_complexity = complexity

        # Последняя группа
        if current_words:
            sub = Subproblem(sub_id, current_words, current_complexity)
            storage.save_subproblem(sub)
            sub_id += 1
            self.logger.debug(f"Subproblem {sub_id-1}: {len(current_words)} words, complexity: {current_complexity}")

        self.subproblems_count = sub_id
        storage.save_metadata(self.subproblems_count)
        self.logger.info(f"Created {self.subproblems_count} subproblems")
        return self.subproblems_count