from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

from ..configs.mask_config import MaskConfig
from .image_processor import ImageProcessor

class MaskManager:
    def __init__(self, config: MaskConfig, panorama_id: str, base_paths: Dict[str, Path], logger=None):
        """Initialize the MaskManager with configuration and paths"""
        self.config = config
        self.panorama_id = panorama_id
        self.base_paths = base_paths
        self.logger = logger
        
        # Cache structures
        self.mask_cache = {}  # Static masks
        self.sequence_paths = {}  # Paths to sequence frames
        self.sequence_max_frames = {}  # Max frame numbers for sequences
        self.sequence_cache = {} # Small cache for recently used sequence frames
        self.max_sequence_cache = 10 # Maximum number of frames to keep in sequence cache
        
        # State tracking
        self.results_index = 0
        self.previous_mask = None
        
        # Create results directory
        self.results_dir = base_paths['results']
        self.results_dir.mkdir(exist_ok=True)
        if self.logger:
            self.logger.log(f"Results directory: {self.results_dir}")

    def load_static_masks(self):
        """Load all static masks defined in configuration"""
        for gray_value in self.config.gray_values:
            # Check both PNG and BMP paths
            bmp_path = self.base_paths['base'] / f"{self.panorama_id}_{gray_value}.bmp"
            png_path = self.base_paths['base'] / f"{self.panorama_id}_{gray_value}.png"
            
            mask_path = bmp_path if bmp_path.exists() else png_path
            if mask_path.exists():
                mask = ImageProcessor.load_and_resize_image(mask_path)
                if mask is not None:
                    _, binary_mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
                    self.mask_cache[gray_value] = binary_mask
                    self.logger.log(f"Loaded static mask for gray value {gray_value}")

    def _get_cache_key(self, gray_value: int, seq_num: int, frame_num: int) -> str:
        """Generate cache key for sequence frame lookup"""
        return f"{gray_value}_{seq_num}_{frame_num}"

    def _cache_sequence_frame(self, gray_value: int, seq_num: int, frame_num: int, frame: np.ndarray):
        """Add sequence frame to cache, removing oldest if needed"""
        key = self._get_cache_key(gray_value, seq_num, frame_num)
        
        # Remove oldest frame if cache is full
        if len(self.sequence_cache) >= self.max_sequence_cache:
            oldest_key = next(iter(self.sequence_cache))
            del self.sequence_cache[oldest_key]
            
        self.sequence_cache[key] = frame
        
    def scan_sequences(self) -> int:
        """Scan for available sequences without loading frames into memory"""
        total_frames = 0
        
        for gray_value in self.config.gray_values:
            gray_dir = self.base_paths['base'] / f"{self.panorama_id}_{gray_value}"
            if not gray_dir.exists():
                continue
            
            self.sequence_paths[gray_value] = {}
            self.sequence_max_frames[gray_value] = {}
            
            seq_dirs = list(sorted(gray_dir.glob(f"{self.panorama_id}_{gray_value}_*")))
            
            for seq_dir in seq_dirs:
                try:
                    seq_num = int(seq_dir.name.split('_')[-1])
                    frame_files = sorted(seq_dir.glob('*.bmp'))
                    
                    # Store paths for on-demand loading
                    frame_paths = {}
                    max_frame = 0
                    
                    for frame_path in frame_files:
                        try:
                            frame_num = int(frame_path.stem.split('_')[-1])
                            frame_paths[frame_num] = frame_path
                            max_frame = max(max_frame, frame_num)
                            total_frames += 1
                        except ValueError:
                            continue
                    
                    if frame_paths:
                        self.sequence_paths[gray_value][seq_num] = frame_paths
                        self.sequence_max_frames[gray_value][seq_num] = max_frame
                        if self.logger:
                            self.logger.log(f"Found sequence {gray_value}_{seq_num} ({self.panorama_id}). {len(frame_paths)} frames available.")
                    
                except ValueError:
                    continue
        
        if self.logger:
            self.logger.log(f"Found total frames: {total_frames}")
        return total_frames
    
    def get_frame(self, gray_value: int, seq_num: int, frame_num: int) -> Optional[np.ndarray]:
        """Load frame from cache or disk"""
        # Try sequence cache first
        cache_key = self._get_cache_key(gray_value, seq_num, frame_num)
        if cache_key in self.sequence_cache:
            return self.sequence_cache[cache_key]
        
        # Load from disk if not in cache
        if gray_value not in self.sequence_paths:
            return None
            
        if seq_num not in self.sequence_paths[gray_value]:
            return None
            
        max_frame = self.sequence_max_frames[gray_value].get(seq_num, 0)
        if max_frame == 0:
            return None
            
        actual_frame = min(frame_num, max_frame)
        frame_path = self.sequence_paths[gray_value][seq_num].get(actual_frame)
        
        if frame_path and frame_path.exists():
            frame = ImageProcessor.load_and_resize_image(frame_path)
            if frame is not None:
                _, binary_frame = cv2.threshold(frame, 127, 255, cv2.THRESH_BINARY)
                
                # Add to sequence cache
                self._cache_sequence_frame(gray_value, seq_num, frame_num, binary_frame)
                return binary_frame
                
        return None

    def process_and_save(self, state: Dict[int, List[Tuple[int, int]]]) -> Optional[Path]:
        """Process current state and save result mask"""
        if not state:
            return None
            
        # Create output mask with background value
        target_size = (1280, 3840)  # height x width
        final_mask = np.full(target_size, 255, dtype=np.uint8)
        
        # Sort gray values by index (highest to lowest) for proper layering
        sorted_gray_values = sorted(
            self.config.gray_values,
            reverse=True
        )
        
        for gray_value in sorted_gray_values:
            active_frames = []
            
            # Add static mask if exists
            if gray_value in self.mask_cache:
                active_frames.append(self.mask_cache[gray_value])
            
            # Add sequence frames
            if gray_value in state:
                for seq_num, frame_num in state[gray_value]:
                    frame = self.get_frame(gray_value, seq_num, frame_num)
                    if frame is not None:
                        active_frames.append(frame)
            
            # Combine all frames
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

    def clear_sequence_cache(self):
        """Clear the sequence frames cache"""
        self.sequence_cache.clear()