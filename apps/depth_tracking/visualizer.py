# visualizer.py
import sys
import numpy as np
import cv2
from .terminal_utils import TerminalUtils

class Visualizer:
    def __init__(self, config):
        self.config = config
        self.frame_initialized = False
        
    def create_buffer(self) -> list[list[str]]:
        return [[" " for _ in range(self.config.nH)] for _ in range(self.config.nV)]

    def create_heatmap(self, distances, mirror=True):
        """Create a CV2 heatmap visualization of the depth data."""
        heatmap = np.array(distances).reshape(self.config.nV, self.config.nH)
        
        if mirror:
            heatmap = np.fliplr(heatmap)
        
        mask = (heatmap >= self.config.MIN_THRESHOLD) & (heatmap <= self.config.MAX_THRESHOLD)
        
        normalized = np.zeros_like(heatmap)
        normalized[mask] = ((heatmap[mask] - self.config.MIN_THRESHOLD) / 
                        (self.config.MAX_THRESHOLD - self.config.MIN_THRESHOLD) * 255)
        normalized = normalized.astype(np.uint8)
        
        heatmap_colored = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
        heatmap_colored[~mask] = [0, 0, 0]
        
        scale_factor = 80
        heatmap_scaled = cv2.resize(heatmap_colored, 
                                (self.config.nH * scale_factor, self.config.nV * scale_factor), 
                                interpolation=cv2.INTER_NEAREST)
        
        return heatmap_scaled

    def create_console_heatmap(self, distances, prev_buffer, mirror=True):
        """Create and update console-based heatmap visualization."""
        if not self.config.SHOW_CONSOLE_PREVIEW:
            return prev_buffer

        heatmap = np.array(distances).reshape(self.config.nV, self.config.nH)
        
        if mirror:
            heatmap = np.fliplr(heatmap)
        
        mask = (heatmap >= self.config.MIN_THRESHOLD) & (heatmap <= self.config.MAX_THRESHOLD)
        normalized = np.zeros_like(heatmap, dtype=float)
        normalized[mask] = ((heatmap[mask] - self.config.MIN_THRESHOLD) / 
                        (self.config.MAX_THRESHOLD - self.config.MIN_THRESHOLD))
        
        chars = ' ░▒▓█'
        current_buffer = [[" " for _ in range(self.config.nH)] for _ in range(self.config.nV)]

        if not self.frame_initialized:
            # Initialize frame
            TerminalUtils.clear_screen()
            TerminalUtils.hide_cursor()
            
            # Draw frame
            TerminalUtils.move_cursor(1, 1)
            print("┏" + "━" * (self.config.nH * 2) + "┓")
            for i in range(self.config.nV):
                TerminalUtils.move_cursor(1, i + 2)
                print("┃" + " " * (self.config.nH * 2) + "┃")
            TerminalUtils.move_cursor(1, self.config.nV + 2)
            print("┗" + "━" * (self.config.nH * 2) + "┛")
            
            # Print static content
            TerminalUtils.move_cursor(1, self.config.nV + 4)
            print(f"Range: {self.config.MIN_THRESHOLD:.1f}m to {self.config.MAX_THRESHOLD:.1f}m")
            TerminalUtils.move_cursor(1, self.config.nV + 5)
            print("Controls:")
            TerminalUtils.move_cursor(1, self.config.nV + 6)
            print("  'q' - Exit")
            TerminalUtils.move_cursor(1, self.config.nV + 7)
            print("  'w' - Toggle window")
            TerminalUtils.move_cursor(1, self.config.nV + 8)
            print("  's' - Toggle stats")
            TerminalUtils.move_cursor(1, self.config.nV + 9)
            print("  'm' - Toggle mirror mode")
            
            self.frame_initialized = True

        # Update heatmap
        for i in range(self.config.nV):
            for j in range(self.config.nH):
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

    def reset_frame(self):
        """Reset frame initialization state"""
        self.frame_initialized = False