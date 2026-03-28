from grid_system_common import Subproblem, DIRECTIONS

class Generator:
    def __init__(self, matrix, words, coefficient, log_manager=None):
        self.matrix = matrix
        self.words = words
        self.coefficient = coefficient
        self.placement_counts = {}
        self.subproblems = []
        self.logger = log_manager.get_logger("generator") if log_manager else None
    
    def compute_placement_counts(self):
        """Вычисление количества возможных размещений для каждого слова."""
        if self.logger:
            self.logger.info(f"Computing placement counts for {len(self.words)} words")
        
        # Построение индекса позиций букв
        letter_positions = {}
        for r, row in enumerate(self.matrix):
            for c, ch in enumerate(row):
                letter_positions.setdefault(ch, []).append((r, c))
        
        # Подсчет размещений для каждого слова
        for word in self.words:
            count = 0
            first_char = word[0]
            for r, c in letter_positions.get(first_char, []):
                for dr, dc in DIRECTIONS:
                    if self._fits(word, r, c, dr, dc):
                        count += 1
            self.placement_counts[word] = count
        
        if self.logger:
            self.logger.info(f"Placement counts computed. Min: {min(self.placement_counts.values())}, Max: {max(self.placement_counts.values())}")
    
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
        if self.logger:
            self.logger.info(f"Creating subproblems with coefficient {self.coefficient}")
        
        # Сортировка слов по убыванию количества размещений для балансировки
        sorted_words = sorted(self.words, key=lambda w: self.placement_counts[w], reverse=True)
        sub_id = 0
        current_words = []
        current_complexity = 0
        
        for word in sorted_words:
            count = self.placement_counts[word]
            
            # Если слово слишком сложное, создаем отдельную подзадачу
            if count > self.coefficient:
                if current_words:
                    self.subproblems.append(Subproblem(sub_id, current_words, current_complexity))
                    sub_id += 1
                    current_words = []
                    current_complexity = 0
                self.subproblems.append(Subproblem(sub_id, [word], count))
                sub_id += 1
                if self.logger:
                    self.logger.debug(f"Single-word subproblem {sub_id-1}: {word} (complexity: {count})")
            else:
                if current_complexity + count <= self.coefficient:
                    current_words.append(word)
                    current_complexity += count
                else:
                    if current_words:
                        self.subproblems.append(Subproblem(sub_id, current_words, current_complexity))
                        sub_id += 1
                        if self.logger:
                            self.logger.debug(f"Subproblem {sub_id-1}: {len(current_words)} words, complexity: {current_complexity}")
                    current_words = [word]
                    current_complexity = count
        
        if current_words:
            self.subproblems.append(Subproblem(sub_id, current_words, current_complexity))
            if self.logger:
                self.logger.debug(f"Subproblem {sub_id}: {len(current_words)} words, complexity: {current_complexity}")
        
        if self.logger:
            self.logger.info(f"Created {len(self.subproblems)} subproblems")