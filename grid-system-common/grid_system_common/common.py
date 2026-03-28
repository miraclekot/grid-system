from dataclasses import dataclass
from typing import List, Tuple

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

@dataclass
class WorkerInfo:
    id: int
    address: str
    busy: bool