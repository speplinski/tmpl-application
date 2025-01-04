import time
from integration.config.integrated_config import IntegratedConfig
from integration.utils.console_logger import ConsoleLogger

class DepthTracker:
    def __init__(self, config: IntegratedConfig):
        self.config = config
        self.logger = ConsoleLogger(name="DepthTracker")
        
        self.threshold_time = 3.0
        self.increment_interval = config.timing.counter_interval
        grid_h, _ = config.depth.grid_dimensions
        self.position_timers = {}
        self.position_counters = [0] * grid_h
        self.last_increment_time = None
        
        # Logging configuration
        self.last_log_state = None
        self.log_filename = 'tmpl.log'
        self._init_log_file()
    
    def _init_log_file(self):
        """Initialize log file"""
        with open(self.log_filename, 'w') as f:
            f.write('')
        self.last_log_state = None
    
    def update(self, column_presence):
        current_time = time.time()
        current_active = [i for i, p in enumerate(column_presence) if p == 1]
        self.logger.log(f"Active columns: {current_active}")
        
        if self.last_increment_time is None:
            self.last_increment_time = current_time
            self._active_columns = set(current_active)
            return
            
        if current_time - self.last_increment_time >= self.increment_interval:
            self.logger.log(f"Incrementing: {self._active_columns}")
            self._increment_counters(list(self._active_columns))
            self.last_increment_time = current_time
            self._active_columns = set(current_active)
        else:
            self._active_columns.update(current_active)

    def _increment_counters(self, positions):
        """Increment counters for active positions"""
        for pos in positions:
            self.position_counters[pos] += 1
        self.log_state()
    
    def log_state(self):
        """Log current counter state"""
        current_state = self.position_counters
        if current_state != self.last_log_state:
            with open(self.log_filename, 'a') as f:
                f.write(f"{current_state}\n")
            self.last_log_state = current_state.copy()