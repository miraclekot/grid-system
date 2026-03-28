from grid_system_common import Subproblem, DIRECTIONS

class Generator:
    def __init__(self, matrix, words, coefficient):
        self.matrix = matrix
        self.words = words
        self.coefficient = coefficient
        self.placement_counts = {}
        self.subproblems = []

    def compute_placement_counts(self):
        # Build index of letter positions
        letter_positions = {}
        for r, row in enumerate(self.matrix):
            for c, ch in enumerate(row):
                letter_positions.setdefault(ch, []).append((r, c))

        # Count placements for each word
        for word in self.words:
            count = 0
            first_char = word[0]
            for r, c in letter_positions.get(first_char, []):
                for dr, dc in DIRECTIONS:
                    if self._fits(word, r, c, dr, dc):
                        count += 1
            self.placement_counts[word] = count

    def _fits(self, word, r, c, dr, dc):
        for i, ch in enumerate(word):
            nr = r + i * dr
            nc = c + i * dc
            if nr < 0 or nr >= len(self.matrix) or nc < 0 or nc >= len(self.matrix[0]):
                return False
            if self.matrix[nr][nc] != ch:
                return False
        return True

    def create_subproblems(self):
        # Sort words by placement count descending to help balance
        sorted_words = sorted(self.words, key=lambda w: self.placement_counts[w], reverse=True)
        sub_id = 0
        current_words = []
        current_complexity = 0

        for word in sorted_words:
            count = self.placement_counts[word]
            if count > self.coefficient:
                # Single‑word subproblem
                if current_words:
                    self.subproblems.append(Subproblem(sub_id, current_words, current_complexity))
                    sub_id += 1
                    current_words = []
                    current_complexity = 0
                self.subproblems.append(Subproblem(sub_id, [word], count))
                sub_id += 1
            else:
                if current_complexity + count <= self.coefficient:
                    current_words.append(word)
                    current_complexity += count
                else:
                    if current_words:
                        self.subproblems.append(Subproblem(sub_id, current_words, current_complexity))
                        sub_id += 1
                    current_words = [word]
                    current_complexity = count

        if current_words:
            self.subproblems.append(Subproblem(sub_id, current_words, current_complexity))