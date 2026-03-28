import json
from pathlib import Path
from typing import Dict, List, Set, Optional

from grid_system_common import Placement, Subproblem, json_serialize, json_deserialize


class PersistentStorage:
    """Хранение состояния вычислений в файловой системе."""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.completed_file = self.storage_dir / "completed_subtasks.txt"
        self.subproblems_file = self.storage_dir / "subproblems.json"
        self.results_file = self.storage_dir / "results.json"
    
    def save_subproblems(self, subproblems: Dict[int, Subproblem]):
        """Сохранить подзадачи."""
        data = {str(k): v for k, v in subproblems.items()}
        with open(self.subproblems_file, 'w', encoding='utf-8') as f:
            f.write(json_serialize(data))
    
    def load_subproblems(self) -> Dict[int, Subproblem]:
        """Загрузить подзадачи."""
        if not self.subproblems_file.exists():
            return {}
        with open(self.subproblems_file, 'r', encoding='utf-8') as f:
            data = json_deserialize(f.read())
            return {int(k): Subproblem(**v) for k, v in data.items()}
    
    def save_completed_subtask(self, subproblem_id: int):
        """Сохранить ID выполненной подзадачи."""
        with open(self.completed_file, 'a', encoding='utf-8') as f:
            f.write(f"{subproblem_id}\n")
    
    def load_completed_subtasks(self) -> Set[int]:
        """Загрузить ID выполненных подзадач."""
        if not self.completed_file.exists():
            return set()
        with open(self.completed_file, 'r', encoding='utf-8') as f:
            return {int(line.strip()) for line in f if line.strip()}
    
    def save_results(self, results: Dict[int, List[Placement]]):
        """Сохранить результаты."""
        data = {
            str(k): [p.to_dict() for p in v]
            for k, v in results.items()
        }
        with open(self.results_file, 'w', encoding='utf-8') as f:
            f.write(json_serialize(data))
    
    def load_results(self) -> Dict[int, List[Placement]]:
        """Загрузить результаты."""
        if not self.results_file.exists():
            return {}
        with open(self.results_file, 'r', encoding='utf-8') as f:
            data = json_deserialize(f.read())
            return {
                int(k): [Placement.from_dict(p) for p in v]
                for k, v in data.items()
            }