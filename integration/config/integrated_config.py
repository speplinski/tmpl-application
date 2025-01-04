from dataclasses import dataclass, field
from typing import Tuple, Optional
from pathlib import Path

@dataclass
class DisplayConfig:
    """Configuration for display and visualization settings"""
    resolution: Tuple[int, int] = (3840, 2160)
    model_resolution: Tuple[int, int] = (3840, 1280)
    show_stats: bool = True
    show_visualization: bool = True
    
    @property
    def resolution_offset(self) -> int:
        """Calculate vertical offset for model display"""
        return (self.resolution[1] - self.model_resolution[1]) >> 1

@dataclass
class TimingConfig:
    """Configuration for various timing-related settings"""
    refresh_interval: float = 0.1
    counter_interval: float = 1.0
    video_trigger: float = 15.0
    fade_duration: float = 2.0
    frame_step: int = 1
    source_fps: float = 1.0
    frames_to_interpolate: int = 30
    
    @property
    def total_fps(self) -> float:
        """Calculate total FPS including interpolation"""
        return self.source_fps * (self.frames_to_interpolate + 1)

@dataclass
class SequenceConfig:
    """Configuration for sequence data paths"""
    overlay_path: str = "data/overlays/default.png"
    video_path: str = "data/movies/default.mp4"

@dataclass
class DepthConfig:
    """Configuration for depth tracking settings"""
    min_threshold: float = 0.4
    max_threshold: float = 1.8
    grid_dimensions: Tuple[int, int] = (10, 6)
    mirror_mode: bool = True
    display_window: bool = False
    buffer_size: int = 4

@dataclass
class SpadeConfig:
    """Configuration for SPADE model settings"""
    bypass_spade: bool = True
    colormap: str = 'viridis'
    device_type: str = 'auto'
    input_dir: Path = Path('results')
    output_dir: Path = Path('output')

@dataclass
class IntegratedConfig:
    """Unified configuration for the entire application"""
    # Core configurations
    display: DisplayConfig = field(default_factory=DisplayConfig)
    timing: TimingConfig = field(default_factory=TimingConfig)
    depth: DepthConfig = field(default_factory=DepthConfig)
    spade: SpadeConfig = field(default_factory=SpadeConfig)
    
    # Current sequence configuration
    sequence: SequenceConfig = field(default_factory=SequenceConfig)
    
    # Feature flags
    enable_mask_generation: bool = True
    enable_depth_tracking: bool = True
    debug_mode: bool = False
    is_running: bool = True
    
    def to_dict(self) -> dict:
        """Convert configuration to dictionary format"""
        return {
            'display': {
                'resolution': self.display.resolution,
                'model_resolution': self.display.model_resolution,
                'show_stats': self.display.show_stats,
                'show_visualization': self.display.show_visualization
            },
            'depth': {
                'min_threshold': self.depth.min_threshold,
                'max_threshold': self.depth.max_threshold,
                'grid_dimensions': self.depth.grid_dimensions,
                'mirror_mode': self.depth.mirror_mode,
                'display_window': self.depth.display_window
            },
            'timing': {
                'refresh_interval': self.timing.refresh_interval,
                'counter_interval': self.timing.counter_interval,
                'video_trigger': self.timing.video_trigger
            },
            'features': {
                'mask_generation': self.enable_mask_generation,
                'depth_tracking': self.enable_depth_tracking,
                'debug': self.debug_mode
            }
        }
    
    def update_from_depth(self, depth_config: dict):
        """Update depth configuration from dictionary"""
        self.depth.min_threshold = depth_config['min_threshold']
        self.depth.max_threshold = depth_config['max_threshold']
        self.depth.grid_dimensions = depth_config['grid_dimensions']
        self.depth.mirror_mode = depth_config['mirror_mode']
        self.depth.display_window = depth_config['display_window']

    @classmethod
    def create_default(cls) -> 'IntegratedConfig':
        """Create configuration with default settings"""
        return cls()