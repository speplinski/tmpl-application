import os
import mmap
from ast import literal_eval
from typing import Optional, List, Tuple
from ..utils.constants import LOG_FILENAME

class FileMonitor:
    """Handles file monitoring and state reading"""
    def __init__(self, filename: str = LOG_FILENAME):
        self.filename = filename
        self.last_modified = 0
        self.last_state = None

    def get_last_state(self) -> Optional[List[int]]:
        """Read last state from file using mmap"""
        try:
            with open(self.filename, 'rb') as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    last_line = mm.readline()
                    while True:
                        next_line = mm.readline()
                        if not next_line:
                            break
                        last_line = next_line
                    return literal_eval(last_line.decode().strip())
        except Exception as e:
            print(f"Error reading state: {e}")
            return None

    def check_for_updates(self) -> Tuple[Optional[List[int]], bool]:
        """Check for file updates and return new state if available"""
        if not os.path.exists(self.filename):
            return None, False

        current_modified = os.path.getmtime(self.filename)
        if current_modified != self.last_modified:
            current_state = self.get_last_state()
            if current_state and current_state != self.last_state:
                self.last_state = current_state
                self.last_modified = current_modified
                return current_state, True
            self.last_modified = current_modified
        
        return None, False