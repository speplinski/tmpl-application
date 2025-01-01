import time
import os
from pathlib import Path
from ..config import IntegratedConfig
from ..adapters import SpadeAdapter
from ..utils.console_logger import ConsoleLogger

class IntegratedSpade:
    def __init__(self, config: IntegratedConfig):
        self.logger = ConsoleLogger(name="Spade")
        self.config = config
        self.file_counter = 1 
        
        # Initialize SPADE
        self.adapter = SpadeAdapter(
            device_type=config.spade_device_type,
            logger=self.logger
        )

        # Ensure directories exist
        self.config.spade_input_dir.mkdir(parents=True, exist_ok=True)
        self.config.spade_output_dir.mkdir(parents=True, exist_ok=True)

    def _get_next_filename(self) -> str:
        """Generate next filename with padding."""
        filename = f"{self.file_counter:09d}.jpg"
        self.file_counter += 1
        return filename

    def watch_and_process(self):
        """Monitor input directory for new masks."""
        try:
            # Get BMP files sorted by creation time
            mask_files = sorted(
                self.config.spade_input_dir.glob("*.bmp"),
                key=lambda x: x.stat().st_ctime
            )
            
            if not mask_files:
                return
                
            # Process oldest file
            mask_file = mask_files[0]
            
            try:
                # Try to process
                if self.process_mask(mask_file.name):
                    # If successful, delete the input file
                    try:
                        os.remove(mask_file)
                    except:
                        pass  # Ignore deletion errors
            except:
                # If any error occurs during processing, just try to delete and continue
                try:
                    os.remove(mask_file)
                except:
                    pass

        except Exception as e:
            self.logger.log(f"Error in processing loop: {e}")

    def process_mask(self, mask_filename: str) -> bool:
        """Process a single mask file."""
        input_path = self.config.spade_input_dir / mask_filename
        output_path = self.config.spade_output_dir / self._get_next_filename()
        
        if not input_path.exists():
            return False
            
        return self.adapter.process_mask(input_path, output_path)