from dataclasses import dataclass
from typing import List, Callable, Optional, Dict, Any
import math


@dataclass
class SubTask:
    """Представление одной подзадачи"""
    task_id: int
    words: List[str]          # Слова для этой подзадачи
    matrix: List[List[str]]   # Полная матрица букв
    metadata: Dict[str, Any]  # Дополнительные метаданные (сложность)


class TaskGenerator:
    """
    Генератор подзадач для грид-системы.
    Формирует подзадачи как (полная матрица + подмножество слов).
    """
    
    def __init__(self, matrix: List[List[str]], words: List[str]):
        """
        Args:
            matrix: полная матрица букв (W x H)
            words: полный словарь слов
        """
        self.matrix = matrix
        self.full_words = words
        self.W = len(matrix[0]) if matrix else 0
        self.H = len(matrix)
        
    def _estimate_word_complexity(self, word: str) -> float:
        """
        Оценивает сложность одного слова в полной матрице.
        Чем длиннее слово и чем больше места в матрице, тем выше сложность.
        """
        L = len(word)
        if L > self.W and L > self.H:
            return 0.0
        
        # Приближённая оценка числа возможных размещений
        horiz = 2 * max(0, self.W - L + 1) * self.H
        vert = 2 * self.W * max(0, self.H - L + 1)
        diag = 4 * max(0, self.W - L + 1) * max(0, self.H - L + 1)
        
        return float(horiz + vert + diag)
    
    def generate_subtasks(
        self,
        target_complexity: float,
        num_subtasks: Optional[int] = None,
        handler: Optional[Callable[[SubTask], None]] = None
    ) -> List[SubTask]:
        """
        Генерирует подзадачи и (опционально) вызывает для каждой handler.
        
        Args:
            target_complexity: целевая сложность одной подзадачи (Cmax)
            num_subtasks: желаемое количество подзадач (если указано,
                          target_complexity может быть переопределён)
            handler: функция-обработчик, вызываемая для каждой подзадачи
                     (если None, просто возвращает список подзадач)
        
        Returns:
            List[SubTask]: список сгенерированных подзадач
        """
        if not self.full_words:
            return []
        
        # Оценка сложности каждого слова
        word_complexities = {
            w: self._estimate_word_complexity(w) 
            for w in self.full_words
        }
        
        # Сортировка слов по сложности (для равномерного распределения)
        words_sorted = sorted(
            self.full_words, 
            key=lambda w: word_complexities[w], 
            reverse=True
        )
        
        # Определение количества подзадач
        if num_subtasks is None:
            # Рассчитываем исходя из target_complexity
            total_complexity = sum(word_complexities.values())
            num_subtasks = max(1, math.ceil(total_complexity / target_complexity))
        
        # Распределение слов по подзадачам (жадное выравнивание)
        tasks_complexities = [0.0] * num_subtasks
        tasks_words = [[] for _ in range(num_subtasks)]
        
        for w in words_sorted:
            # Находим задачу с минимальной текущей сложностью
            min_idx = min(range(num_subtasks), key=lambda i: tasks_complexities[i])
            tasks_words[min_idx].append(w)
            tasks_complexities[min_idx] += word_complexities[w]
        
        # Удаляем пустые задачи
        tasks_words = [tw for tw in tasks_words if tw]
        
        # Формируем объекты подзадач
        subtasks = []
        for idx, words_list in enumerate(tasks_words):
            subtask = SubTask(
                task_id=idx,
                words=words_list,
                matrix=self.matrix,
                metadata={
                    "complexity": tasks_complexities[idx],
                    "num_words": len(words_list)
                }
            )
            subtasks.append(subtask)
        
        # Вызываем handler для каждой подзадачи (если предоставлен)
        if handler is not None:
            for subtask in subtasks:
                handler(subtask)
        
        return subtasks
