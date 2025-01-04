import numpy as np
from integration.config.integrated_config import IntegratedConfig

class ColumnAnalyzer:
    def __init__(self, config: IntegratedConfig):
        self.config = config

    def analyze_columns(self, distances, mirror=True):
        """Analyze columns for object presence."""
        grid_h, grid_v = self.config.depth.grid_dimensions
        heatmap = np.array(distances).reshape(grid_v, grid_h)
        
        if mirror:
            heatmap = np.fliplr(heatmap)
        
        mask = ((heatmap >= self.config.depth.min_threshold) & 
               (heatmap <= self.config.depth.max_threshold))
        
        column_presence = np.zeros(grid_h, dtype=int)
        for col in range(grid_h):
            if np.any(mask[:, col]):
                column_presence[col] = 1
        
        return column_presence