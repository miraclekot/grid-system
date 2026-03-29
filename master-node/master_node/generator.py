from grid_system_common import Subproblem, DIRECTIONS
import logging

class Generator:
    def __init__(self, matrix, words, coefficient, log_manager=None):
        self.matrix = matrix
        self.matrix_h = len(matrix)
        self.matrix_w = len(matrix[0])
        self.words = words
        self.coefficient = coefficient
        self.placement_counts = {}
        self.subproblems = []
        self.logger = log_manager.get_logger("generator") if log_manager else logging.getLogger("generator")
    
    def compute_placement_counts(self):
        """Вычисление количества возможных размещений для каждого слова."""
        self.logger.info(f"Computing placement counts for {len(self.words)} words")
        
        # Построение индекса позиций букв
        letter_positions = {}
        for r, row in enumerate(self.matrix):
            for c, ch in enumerate(row):
                letter_positions.setdefault(ch, []).append((r, c))
        
        # Подсчет размещений для каждого слова
        for idx, word in enumerate(self.words):
            count = 0
            first_char = word[0]
            positions = letter_positions.get(first_char, [])
            
            for r, c in positions:
                for dr, dc in DIRECTIONS:
                    if self._fits(word, r, c, dr, dc):
                        count += 1
            
            self.placement_counts[word] = count
            
            if (idx + 1) % 1000 == 0:
                self.logger.debug(f"Processed {idx + 1}/{len(self.words)} words")
        
        min_count = min(self.placement_counts.values()) if self.placement_counts else 0
        max_count = max(self.placement_counts.values()) if self.placement_counts else 0
        self.logger.info(f"Placement counts computed. Min: {min_count}, Max: {max_count}")
    
    def compute_word_complexity(self, l, h, w):
        """Вычисление сложности размещения слова в матрице."""
        
        # Горизонтали (слева направо и справа налево)
        horiz = 2 * h * max(0, w - l + 1)
        
        # Вертикали (сверху вниз и снизу вверх)
        vert = 2 * w * max(0, h - l + 1)
        
        # Диагонали (основная и побочная в обоих направлениях)
        # Количество квадратов (l x l) внутри прямоугольника (w x h)
        if l > w or l > h:
            diag = 0
        else:
            diag = 4 * (w - l + 1) * (h - l + 1)
            
        return horiz + vert + diag
    
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
        
        # Сортировка слов по убыванию количества размещений для балансировки
        sorted_words = sorted(self.words, key=lambda w: self.placement_counts[w], reverse=True)
        sub_id = 0
        current_words = []
        current_complexity = 0
        
        for word in sorted_words:
            complexity = self.compute_word_complexity(len(word), self.matrix_h, self.matrix_w)
            
            # Если слово не имеет размещений, пропускаем его
            if complexity == 0:
                self.logger.debug(f"Word '{word}' has no placements, skipping")
                continue
            
            # Если слово слишком сложное, создаем отдельную подзадачу
            if complexity > self.coefficient:
                if current_words:
                    self.subproblems.append(Subproblem(sub_id, current_words, current_complexity))
                    sub_id += 1
                    current_words = []
                    current_complexity = 0
                self.subproblems.append(Subproblem(sub_id, [word], complexity))
                sub_id += 1
                self.logger.debug(f"Single-word subproblem {sub_id-1}: {word} (complexity: {complexity})")
            else:
                if current_complexity + complexity <= self.coefficient:
                    current_words.append(word)
                    current_complexity += complexity
                else:
                    if current_words:
                        self.subproblems.append(Subproblem(sub_id, current_words, current_complexity))
                        sub_id += 1
                        self.logger.debug(f"Subproblem {sub_id-1}: {len(current_words)} words, complexity: {current_complexity}")
                    current_words = [word]
                    current_complexity = complexity
        
        if current_words:
            self.subproblems.append(Subproblem(sub_id, current_words, current_complexity))
            self.logger.debug(f"Subproblem {sub_id}: {len(current_words)} words, complexity: {current_complexity}")
        
        self.logger.info(f"Created {len(self.subproblems)} subproblems")