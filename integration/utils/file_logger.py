import logging
from datetime import datetime
from pathlib import Path
import sys

class FileLogger:
   def __init__(self, name: str = "tmpl_app"):
       self.log_dir = Path("logs")
       self.log_dir.mkdir(exist_ok=True)
       
       #timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
       timestamp = datetime.now().strftime("%Y%m%d")
       log_file = self.log_dir / f"{name}_{timestamp}.log"
       
       # Get or create logger instance
       self.logger = logging.getLogger(name)
       
       # Only configure logger if it hasn't been configured before
       if not self.logger.handlers:
           self.logger.setLevel(logging.INFO)
           
           file_handler = logging.FileHandler(log_file)
           file_handler.setLevel(logging.INFO)
           
           formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
           file_handler.setFormatter(formatter)
           
           self.logger.addHandler(file_handler)

   def log(self, message: str):
       self.logger.info(message)