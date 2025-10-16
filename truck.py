
from typing import Optional
from dataclasses import dataclass
@dataclass
class Truck:
    id: int
    state: str = "empty"  # empty, waiting, loading, traveling, unloading, returning
    last_loaded_time: Optional[float] = None
    total_cycles: int = 0
    cycle_start_time: Optional[float] = None