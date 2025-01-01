from typing import Dict
from .terminal_utils import TerminalUtils
from .file_logger import FileLogger

class ConsoleLogger:
    
    _instance_count = 0
    
    def __init__(self, name: str = None):
        self.instance_id = ConsoleLogger._instance_count
        ConsoleLogger._instance_count += 1
        self.name = name or f"Logger_{self.instance_id}"
        
        self.file_logger = FileLogger()
        self.stats_initialized = False
        self.grid_height = 6

    def update_stats(self, stats: Dict[str, str]):
        """Display stats in console"""
        if not self.stats_initialized:
            self._initialize_stats_area()
        
        TerminalUtils.move_cursor(1, self.grid_height + 11)
        print(f"Mirror: {stats['Mirror']} | Columns: {stats['Columns']} | Counters: {stats['Counters']}")

    def log(self, message: str):
        """Log message to file only"""
        self.file_logger.log(message)

    def _initialize_stats_area(self):
        TerminalUtils.move_cursor(1, self.grid_height + 4)
        print(f"Range: 0.4m to 1.8m")
        TerminalUtils.move_cursor(1, self.grid_height + 5)
        print("Controls:")
        TerminalUtils.move_cursor(1, self.grid_height + 6)
        print("  'q' - Exit")
        TerminalUtils.move_cursor(1, self.grid_height + 7)
        print("  'w' - Toggle window")
        TerminalUtils.move_cursor(1, self.grid_height + 8)
        print("  's' - Toggle stats")
        TerminalUtils.move_cursor(1, self.grid_height + 9)
        print("  'm' - Toggle mirror mode")
        self.stats_initialized = True