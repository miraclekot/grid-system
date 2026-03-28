from dataclasses import dataclass, field, asdict, is_dataclass
from typing import List, Tuple, Optional, Any, Dict
from enum import Enum
from datetime import datetime
import json

class EnhancedJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for dataclasses and datetime."""
    def default(self, obj):
        if is_dataclass(obj):
            return asdict(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)

def json_serialize(obj: Any) -> str:
    """Serialize object to JSON."""
    return json.dumps(obj, cls=EnhancedJSONEncoder, indent=2)

def json_deserialize(data: str, obj_type=None):
    """Deserialize JSON to Python object."""
    parsed = json.loads(data)
    if obj_type and is_dataclass(obj_type):
        return obj_type(**parsed)
    return parsed

DIRECTIONS = [
    (0, 1),   # right
    (0, -1),  # left
    (1, 0),   # down
    (-1, 0),  # up
    (1, 1),   # down-right
    (1, -1),  # down-left
    (-1, 1),  # up-right
    (-1, -1)  # up-left
]

class WorkerStatus(Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

@dataclass
class Placement:
    word: str
    row: int
    col: int
    dr: int
    dc: int
    cells: List[Tuple[int, int]]
    
    def to_dict(self):
        return {
            'word': self.word,
            'row': self.row,
            'col': self.col,
            'dr': self.dr,
            'dc': self.dc,
            'cells': [(r, c) for r, c in self.cells]
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            word=data['word'],
            row=data['row'],
            col=data['col'],
            dr=data['dr'],
            dc=data['dc'],
            cells=[(r, c) for r, c in data['cells']]
        )

@dataclass
class Subproblem:
    id: int
    words: List[str]
    complexity: int
    created_at: datetime = field(default_factory=datetime.now)
    assigned_worker: Optional[int] = None
    status: str = "pending"  # pending, assigned, solved, failed
    solved_at: Optional[datetime] = None
    placements: List[Placement] = field(default_factory=list)
    error: Optional[str] = None

@dataclass
class WorkerInfo:
    id: int
    address: str
    status: WorkerStatus = WorkerStatus.AVAILABLE
    last_heartbeat: datetime = field(default_factory=datetime.now)
    current_task: Optional[int] = None
    task_start_time: Optional[datetime] = None

@dataclass
class Heartbeat:
    worker_id: int
    status: WorkerStatus
    current_task: Optional[int]
    timestamp: datetime = field(default_factory=datetime.now)