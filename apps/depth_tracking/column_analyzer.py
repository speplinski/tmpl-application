import numpy as np

class ColumnAnalyzer:
    def __init__(self, config):
        self.config = config

    def analyze_columns(self, distances, mirror=True):
        """
        Analyze columns for object presence and return binary representation.
        Returns array where 1 indicates object presence in column, 0 indicates no object.
        """
        heatmap = np.array(distances).reshape(self.config.nV, self.config.nH)
        if mirror:
            heatmap = np.fliplr(heatmap)
        
        # Create mask for values between thresholds
        mask = (heatmap >= self.config.MIN_THRESHOLD) & (heatmap <= self.config.MAX_THRESHOLD)
        
        # Check each column for object presence
        column_presence = np.zeros(self.config.nH, dtype=int)
        for col in range(self.config.nH):
            if np.any(mask[:, col]):
                column_presence[col] = 1
        
        return column_presence