from typing import Dict, List
from pathlib import Path

# Image processing constants
TARGET_WIDTH = 3840
TARGET_HEIGHT = 1280

# Default output type for images
DEFAULT_IMAGE_TYPE = 'bmp'

# Base paths
def get_base_paths(panorama_id: str) -> Dict[str, Path]:
    return {
        'base': Path(f'./landscapes/{panorama_id}'),
        'sequences': Path(f'./landscapes/{panorama_id}/sequences'),
        'output': Path(f'./landscapes/{panorama_id}'),
        'results': Path('./results')
    }

# File monitoring
MONITORING_INTERVAL = 0.01  # seconds
LOG_FILENAME = 'tmpl.log'

# System constants
MAX_SEQUENCES = 10  # Number of sequence directories to check