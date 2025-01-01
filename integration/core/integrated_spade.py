from pathlib import Path
from ..config import IntegratedConfig
from ..adapters import SpadeAdapter
from ..utils.console_logger import ConsoleLogger

class IntegratedSpade:
    def __init__(self, config: IntegratedConfig):
        self.logger = ConsoleLogger(name="Spade")
        self.config = config
        self.last_processed_mask = None
        
        # Initialize SPADE
        self.adapter = SpadeAdapter(
            device_type=config.spade_device_type,
            logger=self.logger
        )

        # Ensure directories exist
        self.config.spade_input_dir.mkdir(parents=True, exist_ok=True)
        self.config.spade_output_dir.mkdir(parents=True, exist_ok=True)

    def watch_and_process(self):
        """Monitor input directory for new masks."""
        try:
            mask_files = sorted(self.config.spade_input_dir.glob("*.bmp"))
            if not mask_files:
                return
                
            latest_mask = mask_files[-1]
            if latest_mask == self.last_processed_mask:
                return
                
            self.logger.log(f"Found new mask: {latest_mask.name}")
            success = self.process_mask(latest_mask.name)
            
            if success:
                self.last_processed_mask = latest_mask
                
        except Exception as e:
            self.logger.log(f"Error in watch_and_process: {e}")

    def process_mask(self, mask_filename: str) -> bool:
        """Process a single mask file."""
        input_path = self.config.spade_input_dir / mask_filename
        output_path = self.config.spade_output_dir / f"{Path(mask_filename).stem}_gen.jpg"
        
        return self.adapter.process_mask(input_path, output_path)