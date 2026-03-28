# generator.py

from grid_system_common import Subproblem, DIRECTIONS
import logging

class Generator:
    def __init__(self, matrix, words, coefficient, log_manager=None):
        self.matrix = matrix
        self.words = words
        self.coefficient = coefficient
        self.placement_counts = {}
        self.matrix_h = len(matrix)
        self.matrix_w = len(matrix[0])
        self.subproblems = []
        self.logger = log_manager.get_logger("generator") if log_manager else logging.getLogger("generator")
    
    def compute_placement_counts(self):
        """Вычисление количества возможных размещений для каждого слова."""
        self.logger.info(f"Computing placement counts for {len(self.words)} words")
        
        # Подсчет размещений для каждого слова
        for idx, word in enumerate(self.words):           
            self.placement_counts[word] = self.estimate_word_complexity(word)
            
            if (idx + 1) % 1000 == 0:
                self.logger.debug(f"Processed {idx + 1}/{len(self.words)} words")
        
        min_count = min(self.placement_counts.values()) if self.placement_counts else 0
        max_count = max(self.placement_counts.values()) if self.placement_counts else 0
        self.logger.info(f"Placement counts computed. Min: {min_count}, Max: {max_count}")
    
    def estimate_word_complexity(self, word: str) -> float:
        """
        Оценивает количество возможных размещений слова в матрице width x height.
        """
        L = len(word)
        total = 0.0
        
        width = self.matrix_w
        height = self.matrix_h
        
        # Горизонтальные (2 направления)
        if L <= width:
            total += 2.0 * (width - L + 1) * height
        
        # Вертикальные (2 направления)
        if L <= height:
            total += 2.0 * width * (height - L + 1)
        
        # Диагональные (4 направления) — требуют, чтобы слово помещалось по обеим осям
        if L <= width and L <= height:
            total += 4.0 * (width - L + 1) * (height - L + 1)
        
        return total

    def estimate_subtask_complexity(self, words: list[str]) -> float:
        """
        Оценивает суммарную сложность подзадачи.
        """
        
        width = self.matrix_w
        height = self.matrix_h
        
        return sum(self.estimate_word_complexity(w, width, height) for w in words)
    
    def _fits(self, word, r, c, dr, dc):
        """Проверка, помещается ли слово в заданную позицию."""
        for i, ch in enumerate(word):
            nr = r + i * dr
            nc = c + i * dc
            if nr < 0 or nr >= len(self.matrix) or nc < 0 or nc >= len(self.matrix[0]):
                return False
            if self.matrix[nr][nc] != ch:
                return False
        return True
    
    def create_subproblems(self):
        """Создание подзадач на основе коэффициента сложности."""
        self.logger.info(f"Creating subproblems with coefficient {self.coefficient}")
        
        sub_id = 0
        current_words = []
        current_complexity = 0
        
        for word in self.words:
            count = self.placement_counts[word]
            
            # Если слово не имеет размещений, пропускаем его
            if count == 0:
                self.logger.debug(f"Word '{word}' has no placements, skipping")
                continue
            
            # Если слово слишком сложное, создаем отдельную подзадачу
            if count > self.coefficient:
                if current_words:
                    self.subproblems.append(Subproblem(sub_id, current_words, current_complexity))
                    sub_id += 1
                    current_words = []
                    current_complexity = 0
                self.subproblems.append(Subproblem(sub_id, [word], count))
                sub_id += 1
                self.logger.debug(f"Single-word subproblem {sub_id-1}: {word} (complexity: {count})")
            else:
                if current_complexity + count <= self.coefficient:
                    current_words.append(word)
                    current_complexity += count
                else:
                    if current_words:
                        self.subproblems.append(Subproblem(sub_id, current_words, current_complexity))
                        sub_id += 1
                        self.logger.debug(f"Subproblem {sub_id-1}: {len(current_words)} words, complexity: {current_complexity}")
                    current_words = [word]
                    current_complexity = count
        
        if current_words:
            self.subproblems.append(Subproblem(sub_id, current_words, current_complexity))
            self.logger.debug(f"Subproblem {sub_id}: {len(current_words)} words, complexity: {current_complexity}")
        
        self.logger.info(f"Created {len(self.subproblems)} subproblems")