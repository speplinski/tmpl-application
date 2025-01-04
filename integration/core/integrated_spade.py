import json
import time
import os
from pathlib import Path

from apps.generator.utils.dynamic_config import get_project_root
from ..config import IntegratedConfig
from ..adapters import SpadeAdapter
from ..utils.console_logger import ConsoleLogger

class IntegratedSpade:
    def __init__(self, config: IntegratedConfig):
        self.logger = ConsoleLogger(name="Spade")
        self.config = config
        self.file_counter = 1
        project_root = get_project_root()
        mapping_path = project_root / 'data' / 'mask_mapping.json'
        with open(mapping_path) as f:
            mask_mappings = json.load(f)
        self.current_panorama_id = list(mask_mappings.keys())[0]
        
        self.adapter = SpadeAdapter(config=config, logger=self.logger)

        self.config.spade.input_dir.mkdir(parents=True, exist_ok=True)
        self.config.spade.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_next_filename(self) -> str:
        filename = f"{self.file_counter:09d}.jpg"
        self.file_counter += 1
        return filename

    def watch_and_process(self):
        try:
            mask_files = sorted(
                self.config.spade.input_dir.glob("*.bmp"),
                key=lambda x: x.stat().st_ctime
            )
            
            if not mask_files:
                return
                
            mask_file = mask_files[0]
            
            try:
                if self.process_mask(mask_file.name):
                    try:
                        os.remove(mask_file)
                    except:
                        pass
            except:
                try:
                    os.remove(mask_file)
                except:
                    pass

        except Exception as e:
            self.logger.log(f"Error in processing loop: {e}")

    def process_mask(self, mask_filename: str) -> bool:
        input_path = self.config.spade.input_dir / mask_filename
        output_path = self.config.spade.output_dir / self._get_next_filename()
        
        if not input_path.exists():
            return False
            
        return self.adapter.process_mask(input_path, output_path)
    
    def reset_state(self):
        """Reset SPADE state."""
        self.file_counter = 1