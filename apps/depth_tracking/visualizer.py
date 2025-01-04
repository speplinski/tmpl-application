import sys
import numpy as np
import cv2
from integration.config.integrated_config import IntegratedConfig
from .terminal_utils import TerminalUtils

class Visualizer:
    def __init__(self, config: IntegratedConfig):
        self.config = config
        self.frame_initialized = False
        
    def create_buffer(self) -> list[list[str]]:
        grid_h, grid_v = self.config.depth.grid_dimensions
        return [[" " for _ in range(grid_h)] for _ in range(grid_v)]

    def create_heatmap(self, distances, mirror=True):
        """Create CV2 heatmap visualization."""
        grid_h, grid_v = self.config.depth.grid_dimensions
        heatmap = np.array(distances).reshape(grid_v, grid_h)
        
        if mirror:
            heatmap = np.fliplr(heatmap)
        
        mask = ((heatmap >= self.config.depth.min_threshold) & 
               (heatmap <= self.config.depth.max_threshold))
        
        normalized = np.zeros_like(heatmap)
        normalized[mask] = ((heatmap[mask] - self.config.depth.min_threshold) / 
                        (self.config.depth.max_threshold - self.config.depth.min_threshold) * 255)
        normalized = normalized.astype(np.uint8)
        
        heatmap_colored = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
        heatmap_colored[~mask] = [0, 0, 0]
        
        scale_factor = 80
        return cv2.resize(heatmap_colored, 
                       (grid_h * scale_factor, grid_v * scale_factor), 
                       interpolation=cv2.INTER_NEAREST)

    def create_console_heatmap(self, distances, prev_buffer, mirror=True):
        """Create and update console-based heatmap."""
        if not self.config.display.show_visualization:
            return prev_buffer

        grid_h, grid_v = self.config.depth.grid_dimensions
        heatmap = np.array(distances).reshape(grid_v, grid_h)
        
        if mirror:
            heatmap = np.fliplr(heatmap)
        
        mask = ((heatmap >= self.config.depth.min_threshold) & 
               (heatmap <= self.config.depth.max_threshold))
               
        normalized = np.zeros_like(heatmap, dtype=float)
        normalized[mask] = ((heatmap[mask] - self.config.depth.min_threshold) / 
                        (self.config.depth.max_threshold - self.config.depth.min_threshold))
        
        chars = ' ░▒▓█'
        current_buffer = [[" " for _ in range(grid_h)] for _ in range(grid_v)]

        if not self.frame_initialized:
            self._initialize_frame(grid_h, grid_v)
            self.frame_initialized = True

        # Update heatmap
        for i in range(grid_v):
            for j in range(grid_h):
                if mask[i, j]:
                    char_idx = int(normalized[i, j] * (len(chars) - 1))
                    current_char = chars[char_idx]
                else:
                    current_char = " "
                
                current_buffer[i][j] = current_char
                
                if current_char != prev_buffer[i][j]:
                    TerminalUtils.move_cursor(j * 2 + 2, i + 2)
                    sys.stdout.write(f"\033[94m{current_char}\033[0m ")
                    sys.stdout.flush()
        
        return current_buffer

    def _initialize_frame(self, grid_h: int, grid_v: int):
        """Initialize terminal frame."""
        TerminalUtils.clear_screen()
        TerminalUtils.hide_cursor()
        
        # Draw frame
        TerminalUtils.move_cursor(1, 1)
        print("┏" + "━" * (grid_h * 2) + "┓")
        for i in range(grid_v):
            TerminalUtils.move_cursor(1, i + 2)
            print("┃" + " " * (grid_h * 2) + "┃")
        TerminalUtils.move_cursor(1, grid_v + 2)
        print("┗" + "━" * (grid_h * 2) + "┛")
        
        # Print static content
        TerminalUtils.move_cursor(1, grid_v + 4)
        print(f"Range: {self.config.depth.min_threshold:.1f}m to {self.config.depth.max_threshold:.1f}m")
        
        controls = [
            "Controls:",
            "  'q' - Exit",
            "  'w' - Toggle window",
            "  's' - Toggle stats",
            "  'm' - Toggle mirror mode"
        ]
        
        for idx, text in enumerate(controls):
            TerminalUtils.move_cursor(1, grid_v + 5 + idx)
            print(text)

    def reset_frame(self):
        """Reset frame state."""
        self.frame_initialized = False