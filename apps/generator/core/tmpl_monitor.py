# tmpl_monitor.py
from pathlib import Path
from typing import List

from ..configs.mask_config import MaskConfig
from .mask_manager import MaskManager

class TMPLMonitor:
    def __init__(self, panorama_id: str, mask_configs: List[MaskConfig], logger=None):
        self.panorama_id = panorama_id
        self.logger = logger
        
        # Setup paths
        self.base_paths = {
            'base': Path(f'./landscapes/{panorama_id}'),
            'sequences': Path(f'./landscapes/{panorama_id}/sequences'),
            'output': Path(f'./landscapes/{panorama_id}'),
            'results': Path('./results')
        }
        self.base_paths['results'].mkdir(exist_ok=True)
        
        # Initialize components
        self.mask_managers = {
            config.name: MaskManager(config, panorama_id, self.base_paths)
            for config in mask_configs
        }

    def process_state(self, state: List[int]):
        """Process state for all configurations"""
        if not state or not any(state):
            return

        try:
            active_sequences = []
            for seq_num, frame_num in enumerate(state):
                if frame_num > 0:
                    active_sequences.append((seq_num, frame_num))
            
            # Process each configuration
            for name, manager in self.mask_managers.items():
                config_state = {}
                for gray_value in manager.config.gray_values:
                    config_state[gray_value] = active_sequences
            
                result_path = manager.process_and_save(config_state)
                if result_path and self.logger:
                    self.logger.log(f"Generated: {result_path.name}")
        
        except Exception as e:
            if self.logger:
                self.logger.log(f"Error: {e}")
            raise