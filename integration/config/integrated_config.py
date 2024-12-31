from dataclasses import dataclass, field
from typing import Tuple, Dict, Any
from apps.depth_tracking.config import Config as DepthConfig
from apps.generator.configs.mask_config import MaskConfig

@dataclass
class IntegratedConfig:
    """
    Integrated configuration combining settings from all components
    """
    # Depth tracking configuration
    min_depth_threshold: float = 0.4  # meters
    max_depth_threshold: float = 1.8  # meters
    grid_dimensions: Tuple[int, int] = (10, 6)  # (horizontal, vertical)
    mirror_mode: bool = True
    display_window: bool = False
    
    # Stats and display configuration
    show_stats: bool = True
    show_visualization: bool = True
    
    # Timing configuration
    ui_refresh_interval: float = 0.04  # seconds (40ms)
    counter_increment_interval: float = 0.5  # seconds (500ms)
    mask_update_interval: float = 0.1  # seconds (100ms)
    
    # Integration settings
    enable_mask_generation: bool = True
    enable_depth_tracking: bool = True
    
    # Runtime states
    is_running: bool = True
    debug_mode: bool = False

    def to_depth_config(self) -> DepthConfig:
        """Convert to depth tracking configuration"""
        depth_config = DepthConfig()
        # Distance thresholds
        depth_config.MIN_THRESHOLD = self.min_depth_threshold
        depth_config.MAX_THRESHOLD = self.max_depth_threshold
        
        # Display settings
        depth_config.DISPLAY_WINDOW = self.display_window
        depth_config.SHOW_STATS = self.show_stats
        depth_config.MIRROR_MODE = self.mirror_mode
        
        # Timing settings
        depth_config.UI_REFRESH_INTERVAL = self.ui_refresh_interval
        depth_config.COUNTER_INCREMENT_INTERVAL = self.counter_increment_interval
        
        # Grid dimensions
        depth_config.nH, depth_config.nV = self.grid_dimensions
        
        return depth_config

    def update_from_depth(self, depth_config: Dict[str, Any]):
        """Update from depth tracking configuration dictionary"""
        # Update thresholds
        self.min_depth_threshold = depth_config['min_threshold']
        self.max_depth_threshold = depth_config['max_threshold']
        
        # Update dimensions and modes
        self.grid_dimensions = depth_config['grid_dimensions']
        self.mirror_mode = depth_config['mirror_mode']
        self.display_window = depth_config['display_window']

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'depth_tracking': {
                'min_threshold': self.min_depth_threshold,
                'max_threshold': self.max_depth_threshold,
                'grid_dimensions': self.grid_dimensions,
                'mirror_mode': self.mirror_mode,
                'display_window': self.display_window,
                'show_stats': self.show_stats
            },
            'timing': {
                'ui_refresh': self.ui_refresh_interval,
                'counter_increment': self.counter_increment_interval,
                'mask_update': self.mask_update_interval
            },
            'features': {
                'mask_generation': self.enable_mask_generation,
                'depth_tracking': self.enable_depth_tracking,
                'visualization': self.show_visualization,
                'debug': self.debug_mode
            }
        }

    @classmethod
    def create_default(cls) -> 'IntegratedConfig':
        """Create configuration with default settings"""
        return cls()