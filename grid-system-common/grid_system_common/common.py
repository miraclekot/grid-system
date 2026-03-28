from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from enum import Enum
from datetime import datetime

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

@dataclass
class Subproblem:
    id: int
    words: List[str]
    complexity: int
    created_at: datetime = field(default_factory=datetime.now)
    assigned_worker: Optional[int] = None
    status: str = "pending"  # pending, assigned, solved, failed

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