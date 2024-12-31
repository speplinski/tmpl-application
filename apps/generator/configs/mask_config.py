from dataclasses import dataclass
from typing import List, Dict

@dataclass
class MaskConfig:
    """Configuration for a specific mask type"""
    name: str
    gray_values: List[int]
    gray_indexes: Dict[int, int]