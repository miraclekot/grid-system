# master-node/master_node/storage.py
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Iterator
from grid_system_common import Placement, Subproblem, json_serialize, json_deserialize

class PersistentStorage:
    """Хранение состояния вычислений в файловой системе (потоково)."""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.completed_file = self.storage_dir / "completed_subtasks.txt"
        self.subproblems_file = self.storage_dir / "subproblems.jsonl"   # JSON Lines
        self.results_file = self.storage_dir / "results.jsonl"           # JSON Lines
        self.metadata_file = self.storage_dir / "metadata.json"

    def save_subproblem(self, subproblem: Subproblem):
        """Дописать одну подзадачу в файл."""
        with open(self.subproblems_file, 'a', encoding='utf-8') as f:
            f.write(json_serialize(subproblem) + '\n')

    def save_metadata(self, total_subproblems: int):
        """Сохранить метаданные (общее количество подзадач)."""
        metadata = {"total_subproblems": total_subproblems}
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def load_metadata(self) -> dict:
        """Загрузить метаданные."""
        if not self.metadata_file.exists():
            return {"total_subproblems": 0}
        with open(self.metadata_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def iter_subproblems(self) -> Iterator[Subproblem]:
        """Итератор по всем подзадачам из файла."""
        if not self.subproblems_file.exists():
            return
        with open(self.subproblems_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    yield json_deserialize(line, Subproblem)

    def load_subproblem_by_id(self, sub_id: int) -> Optional[Subproblem]:
        """Загрузить конкретную подзадачу по ID (перебором). Для больших файлов неэффективно,
        но в учебных целях допустимо. Для production лучше использовать индекс."""
        for sub in self.iter_subproblems():
            if sub.id == sub_id:
                return sub
        return None

    def save_completed_subtask(self, subproblem_id: int):
        """Дописать ID выполненной подзадачи."""
        with open(self.completed_file, 'a', encoding='utf-8') as f:
            f.write(f"{subproblem_id}\n")

    def load_completed_subtasks(self) -> Set[int]:
        """Загрузить ID выполненных подзадач."""
        if not self.completed_file.exists():
            return set()
        with open(self.completed_file, 'r', encoding='utf-8') as f:
            return {int(line.strip()) for line in f if line.strip()}

    def save_result(self, subproblem_id: int, placements: List[Placement]):
        """Сохранить результат одной подзадачи в JSON Lines."""
        data = {
            "id": subproblem_id,
            "placements": [p.to_dict() for p in placements]
        }
        with open(self.results_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')

    def load_all_results(self) -> Dict[int, List[Placement]]:
        """Загрузить все результаты (для финального покрытия)."""
        results = {}
        if not self.results_file.exists():
            return results
        with open(self.results_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    sub_id = data["id"]
                    placements = [Placement.from_dict(p) for p in data["placements"]]
                    results[sub_id] = placements
        return results