# integrated_depth.py
import time
import cv2
import threading
from threading import Lock
from typing import Optional, Dict, Any, Tuple

from ..config import IntegratedConfig
from ..adapters import DepthMaskAdapter

class IntegratedDepth:
    def __init__(self, config: IntegratedConfig):
        self.config = config
        self.adapter = DepthMaskAdapter()
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = Lock()
        
        self._latest_data: Optional[Dict[str, Any]] = None
        self._latest_heatmap: Optional[cv2.Mat] = None
        self._last_update_time = 0.0
        self._error_state = False
        self.prev_buffer = None

    def start(self) -> bool:
        if self._running:
            return True
            
        if not self.adapter.initialize():
            self._error_state = True
            return False
            
        self.prev_buffer = self.adapter.visualizer.create_buffer()
        self._running = True
        self._thread = threading.Thread(target=self._processing_loop)
        self._thread.daemon = True
        self._thread.start()
        
        return True

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
            self._thread = None
        self.adapter.cleanup()

    def get_latest_data(self) -> Tuple[Optional[Dict[str, Any]], Optional[cv2.Mat]]:
        with self._lock:
            return self._latest_data, self._latest_heatmap

    def update_config(self, new_config: IntegratedConfig):
        with self._lock:
            self.config = new_config
            self.adapter.config.MIRROR_MODE = new_config.mirror_mode
            self.adapter.config.DISPLAY_WINDOW = new_config.display_window
            self.adapter.config.SHOW_STATS = new_config.show_stats
            self.adapter.config.SHOW_CONSOLE_PREVIEW = new_config.show_visualization

    def _processing_loop(self):
        try:
            while self._running:
                try:
                    current_time = time.time()
                    frame_data, heatmap = self.adapter.process_frame()
                    
                    if self.config.show_visualization:
                        self.prev_buffer = self.adapter.visualizer.create_console_heatmap(
                            frame_data['distances'], 
                            self.prev_buffer, 
                            self.config.mirror_mode
                        )
                    
                    with self._lock:
                        self._latest_data = frame_data
                        if self.config.show_visualization:
                            self._latest_heatmap = heatmap
                        self._last_update_time = current_time
                    
                    # Handle window display
                    if self.config.display_window and heatmap is not None:
                        cv2.imshow("Depth Heatmap", heatmap)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            self._running = False
                            break
                    
                    sleep_time = self.config.ui_refresh_interval - (time.time() - current_time)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                        
                except Exception as e:
                    print(f"Error in depth processing: {str(e)}")
                    self._error_state = True
                    self._running = False
                    break
                    
        finally:
            if self.config.display_window:
                cv2.destroyAllWindows()
            
    @property
    def is_running(self) -> bool:
        return self._running and not self._error_state

    def is_error_state(self) -> bool:
        return self._error_state