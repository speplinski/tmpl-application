from pathlib import Path
import json
from typing import Dict, List, Tuple
import os

def get_project_root() -> Path:
    """Returns the path to the Generator directory"""
    current_file = Path(__file__)
    return current_file.parent.parent.parent.parent  # Generator directory

def get_landscapes_dir() -> Path:
    """Returns the path to the landscapes directory"""
    return get_project_root() / 'data' / 'landscapes'

def load_mask_mapping(panorama_id: str) -> Dict:
    """Loads mask to index mapping from configuration file"""
    project_root = get_project_root()
    mapping_file = project_root / 'data' / 'mask_mapping.json'
    
    print(f"Looking for mapping file at: {mapping_file}")
    
    if not mapping_file.exists():
        raise FileNotFoundError(f"Mapping file not found at: {mapping_file}")
        
    with open(mapping_file, 'r') as f:
        mappings = json.load(f)
        
    if panorama_id not in mappings:
        raise ValueError(f"No mapping found for panorama {panorama_id}")
        
    return mappings[panorama_id]

def scan_directory(panorama_id: str) -> Tuple[List[int], Dict[int, int]]:
    """Scans directory for masks and uses defined mapping"""
    landscapes_dir = get_landscapes_dir()
    base_dir = landscapes_dir / panorama_id
    
    print(f"Project root: {get_project_root()}")
    print(f"Landscapes dir: {landscapes_dir}")
    print(f"Scanning directory: {base_dir}")
    
    if not base_dir.exists():
        raise ValueError(f"Directory not found: {base_dir}")

    # Load mapping from configuration file
    mapping = load_mask_mapping(panorama_id)
    static_mapping = {int(k): v for k, v in mapping['static_masks'].items()}
    sequence_mapping = {int(k): v for k, v in mapping['sequence_masks'].items()}

    # Find all PNG files (static masks)
    static_masks = set()
    for png_file in base_dir.glob(f"{panorama_id}_*.png"):
        try:
            gray_value = int(png_file.stem.split('_')[-1])
            if gray_value in static_mapping:
                static_masks.add(gray_value)
        except (ValueError, IndexError):
            continue

    # Find all sequence directories
    sequence_masks = set()
    for directory in base_dir.glob(f"{panorama_id}_*"):
        if directory.is_dir():
            try:
                gray_value = int(directory.name.split('_')[-1])
                if gray_value in sequence_mapping:
                    sequence_masks.add(gray_value)
            except (ValueError, IndexError):
                continue

    # Combine all found values and their mappings
    gray_indexes = {}
    gray_indexes.update(static_mapping)
    gray_indexes.update(sequence_mapping)
    
    # List of all found gray values
    all_gray_values = sorted(static_masks | sequence_masks)

    print("\nFound masks:")
    print(f"Static masks (PNG): {sorted(static_masks)}")
    print(f"Sequence masks (directories): {sorted(sequence_masks)}")
    print(f"Gray value to index mapping: {gray_indexes}")

    return all_gray_values, gray_indexes

def create_dynamic_config(panorama_id: str) -> Dict:
    """Creates configuration based on directory contents and mapping"""
    gray_values, gray_indexes = scan_directory(panorama_id)
    
    return {
        'name': "dynamic",
        'gray_values': gray_values,
        'gray_indexes': gray_indexes
    }