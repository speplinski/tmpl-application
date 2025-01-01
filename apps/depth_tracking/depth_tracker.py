import time

from .config import Config

class DepthTracker:
    """
    Tracks object presence in specific positions over time and logs sustained presence.
    Only increments counters once every 500ms after initial 3-second threshold.
    """
    def __init__(self):
        self.config = Config()
        
        # Time and counting configuration
        self.threshold_time = 3.0  # seconds required before starting to count
        self.increment_interval = self.config.COUNTER_INCREMENT_INTERVAL
        
        # Tracking dictionaries
        self.position_timers = {}  # when position became active
        self.last_increment_time = {}  # when position was last incremented
        self.position_counters = [0] * 10  # counters for all 10 positions
        
        # Logging configuration
        self.last_log_state = None
        self.log_filename = 'tmpl.log'
        
        # Initialize log file
        with open(self.log_filename, 'w') as f:
            f.write('')  # Clear/create file

    def update(self, column_presence):
        """
        Updates tracking state and generates log if needed.
        
        Args:
            column_presence: List of binary values indicating presence (1) or absence (0)
        """
        current_time = time.time()
        changed = False

        # Check all positions (0-9)
        for i in range(10):
            if i < len(column_presence):
                if column_presence[i] == 1:
                    # Start tracking if position is newly active
                    if i not in self.position_timers:
                        self.position_timers[i] = current_time
                        self.last_increment_time[i] = current_time
                    else:
                        # Check if we've passed initial threshold and increment interval
                        time_active = current_time - self.position_timers[i]
                        time_since_last_increment = current_time - self.last_increment_time[i]
                        
                        if (time_active >= self.threshold_time and 
                            time_since_last_increment >= self.increment_interval):
                            # Increment counter and update last increment time
                            self.position_counters[i] += 1
                            self.last_increment_time[i] = current_time
                            # Log state immediately after increment
                            self.log_state()
                else:
                    # Reset timers if position is no longer active
                    if i in self.position_timers:
                        del self.position_timers[i]
                        del self.last_increment_time[i]

    def log_state(self):
        """Logs the current state of counters to file"""
        current_state = self.position_counters
        if current_state != self.last_log_state:
            with open(self.log_filename, 'a') as f:
                f.write(f"{current_state}\n")
            self.last_log_state = current_state.copy()