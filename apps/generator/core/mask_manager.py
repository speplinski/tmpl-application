# mask_manager.py
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

from ..configs.mask_config import MaskConfig

class MaskManager:
    def __init__(self, config: MaskConfig, panorama_id: str, base_paths: Dict[str, Path]):
        self.config = config
        self.panorama_id = panorama_id
        self.base_paths = base_paths
        self.mask_cache = {}
        self.sequence_frames = {}
        self.sequence_max_frames = {}
        self.results_index = 0
        
        # Create results directory
        self.results_dir = base_paths['results']
        self.results_dir.mkdir(exist_ok=True)

    def process_and_save(self, state: Dict[int, List[Tuple[int, int]]]) -> Optional[Path]:
        """Process current state and save result mask."""
        if not state:
            return None
            
        # Create output mask with background value
        target_size = (1280, 3840)  # height x width for numpy
        final_mask = np.full(target_size, 255, dtype=np.uint8)
        
        # Sort gray values by their corresponding indexes (highest first)
        sorted_gray_values = sorted(
            self.config.gray_values,
            key=lambda x: self.config.gray_indexes.get(x, 0),
            reverse=True
        )
        
        # Process masks in sorted order
        for gray_value in sorted_gray_values:
            active_frames = []
            
            # Add static mask if exists
            if gray_value in self.mask_cache:
                active_frames.append(self.mask_cache[gray_value])
            
            # Add sequence frames if present in state
            if gray_value in state:
                for seq_num, frame_num in state[gray_value]:
                    frame = self.get_frame(gray_value, seq_num, frame_num)
                    if frame is not None:
                        active_frames.append(frame)
            
            # Combine frames if any exist
            if active_frames:
                if len(active_frames) > 1:
                    combined_mask = np.maximum.reduce(active_frames)
                else:
                    combined_mask = active_frames[0]
                
                if gray_value in self.config.gray_indexes:
                    index = self.config.gray_indexes[gray_value]
                    final_mask[combined_mask > 0] = index

        # Save result
        next_index = self.results_index + 1
        result_path = self.results_dir / f"{next_index}.bmp"
        cv2.imwrite(str(result_path), final_mask)
        self.results_index = next_index
        
        return result_path

    def get_frame(self, gray_value: int, seq_num: int, frame_num: int) -> Optional[np.ndarray]:
        """Get specific frame from sequence cache."""
        if gray_value not in self.sequence_frames:
            return None
            
        if seq_num not in self.sequence_frames[gray_value]:
            return None
            
        max_frame = self.sequence_max_frames[gray_value].get(seq_num, 0)
        if max_frame == 0:
            return None
            
        actual_frame = min(frame_num, max_frame)
        return self.sequence_frames[gray_value][seq_num].get(actual_frame)