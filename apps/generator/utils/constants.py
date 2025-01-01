from typing import Dict, List
from pathlib import Path
from apps.generator.utils.dynamic_config import get_project_root

# Image processing constants
TARGET_WIDTH = 3840
TARGET_HEIGHT = 1280

# Default output type for images
DEFAULT_IMAGE_TYPE = 'bmp'

# Base paths
def get_base_paths(panorama_id: str) -> Dict[str, Path]:
    project_root = get_project_root()
    return {
        'base': project_root / 'data' / 'landscapes' / panorama_id,
        'sequences': project_root / 'data' / 'landscapes' / panorama_id / 'sequences',
        'output': project_root / 'data' / 'landscapes' / panorama_id,
        'results': project_root / 'results'
    }

# File monitoring
MONITORING_INTERVAL = 0.01  # seconds
LOG_FILENAME = 'tmpl.log'

# System constants
MAX_SEQUENCES = 10  # Number of sequence directories to check