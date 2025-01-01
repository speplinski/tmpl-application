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
        self.mask_cache = {}
        self.sequence_frames = {}
        self.sequence_max_frames = {}
        self.results_index = 0
        self.previous_mask = None
        
        # Create results directory
        self.results_dir = base_paths['results']
        self.results_dir.mkdir(exist_ok=True)
        if self.logger:
            self.logger.log(f"Results directory: {self.results_dir}")

    def log(self, message: str):
        """Helper method for logging"""
        if self.logger:
            self.logger.log(message)

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

    def load_sequence_frames(self) -> int:
        """Load all sequence frames for each configured gray value"""
        total_frames = 0
        frames_to_load = 0  # licznik wszystkich klatek do załadowania
        frames_loaded = 0   # licznik załadowanych klatek
        
        # Najpierw policz wszystkie klatki
        for gray_value in self.config.gray_values:
            gray_dir = self.base_paths['base'] / f"{self.panorama_id}_{gray_value}"
            if gray_dir.exists():
                seq_dirs = list(sorted(gray_dir.glob(f"{self.panorama_id}_{gray_value}_*")))
                for seq_dir in seq_dirs:
                    frame_files = list(seq_dir.glob('*.bmp'))
                    frames_to_load += len(frame_files)
        
        if self.logger:
            self.logger.log(f"Total frames to load: {frames_to_load}")
            
        # Teraz ładuj klatki z logowaniem postępu
        for gray_value in self.config.gray_values:
            gray_dir = self.base_paths['base'] / f"{self.panorama_id}_{gray_value}"
            if not gray_dir.exists():
                continue
            
            self.sequence_frames[gray_value] = {}
            self.sequence_max_frames[gray_value] = {}
            
            seq_dirs = list(sorted(gray_dir.glob(f"{self.panorama_id}_{gray_value}_*")))
            
            for seq_dir in seq_dirs:
                try:
                    seq_num = int(seq_dir.name.split('_')[-1])
                    self.sequence_frames[gray_value][seq_num] = {}
                    
                    frame_files = sorted(seq_dir.glob('*.bmp'))
                    max_frame = 0
                    loaded_frames = 0
                    
                    for frame_path in frame_files:
                        try:
                            frame_num = int(frame_path.stem.split('_')[-1])
                            frame = ImageProcessor.load_and_resize_image(frame_path)
                            if frame is not None:
                                _, binary_frame = cv2.threshold(frame, 127, 255, cv2.THRESH_BINARY)
                                self.sequence_frames[gray_value][seq_num][frame_num] = binary_frame
                                max_frame = max(max_frame, frame_num)
                                loaded_frames += 1
                                frames_loaded += 1
                                
                                # Log progress every 100 frames
                                if frames_loaded % 100 == 0:
                                    progress = (frames_loaded / frames_to_load) * 100
                                    if self.logger:
                                        self.logger.log(f"Progress: {frames_loaded}/{frames_to_load} ({progress:.1f}%)")
                        except ValueError:
                            continue
                    
                    if loaded_frames > 0:
                        self.sequence_max_frames[gray_value][seq_num] = max_frame
                        total_frames += loaded_frames
                        if self.logger:
                            self.logger.log(f"Completed sequence {gray_value}_{seq_num} ({self.panorama_id}). {loaded_frames} frames loaded.")
                    
                except ValueError:
                    continue
        
        if self.logger:
            self.logger.log(f"Completed loading all frames: {total_frames}")
        return total_frames

    def _masks_are_different(self, new_mask: np.ndarray) -> bool:
        """Compare new mask with previous mask"""
        if self.previous_mask is None:
            return True
        return not np.array_equal(new_mask, self.previous_mask)

    def get_frame(self, gray_value: int, seq_num: int, frame_num: int) -> Optional[np.ndarray]:
        """Get specific frame from sequence cache"""
        if gray_value not in self.sequence_frames:
            return None
            
        if seq_num not in self.sequence_frames[gray_value]:
            return None
            
        max_frame = self.sequence_max_frames[gray_value].get(seq_num, 0)
        if max_frame == 0:
            return None
            
        actual_frame = min(frame_num, max_frame)
        return self.sequence_frames[gray_value][seq_num].get(actual_frame)

    def process_and_save(self, state: Dict[int, List[Tuple[int, int]]]) -> Optional[Path]:
        """Process current state and save result mask"""
        if not state:
            return None
            
        #self.log(f"\nProcessing state: {state}")
        
        # Create output mask
        target_size = (1280, 3840)
        final_mask = np.full(target_size, 255, dtype=np.uint8)
        
        # Sort gray values
        sorted_gray_values = sorted(
            self.config.gray_values,
            key=lambda x: self.config.gray_indexes.get(x, 0),
            reverse=True
        )
        
        #self.log("\nProcessing order:")
        #for gray_value in sorted_gray_values:
            #if gray_value in self.config.gray_indexes:
                #self.log(f"Gray value: {gray_value} -> Index: {self.config.gray_indexes[gray_value]}")
        
        # Process masks in order
        for gray_value in sorted_gray_values:
            #self.log(f"\nProcessing gray value: {gray_value}")
            active_frames = []
            
            # Add static mask if exists
            if gray_value in self.mask_cache:
                #self.log(f"Found static mask for {gray_value}")
                active_frames.append(self.mask_cache[gray_value])
            
            # Add sequence frames if present
            if gray_value in state:
                #self.log(f"Processing sequences for {gray_value}: {state[gray_value]}")
                for seq_num, frame_num in state[gray_value]:
                    frame = self.get_frame(gray_value, seq_num, frame_num)
                    if frame is not None:
                        #self.log(f"Added frame {frame_num} from sequence {seq_num}")
                        active_frames.append(frame)
            
            # Combine frames
            if active_frames:
                #self.log(f"Combining {len(active_frames)} frames for gray value {gray_value}")
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
        #self.log(f"\nSaving result to: {result_path}")
        cv2.imwrite(str(result_path), final_mask)
        self.results_index = next_index
        
        return result_path