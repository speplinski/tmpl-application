class Config:
    def __init__(self):
        # Distance thresholds (in meters)
        self.MIN_THRESHOLD = 0.4  # 40 cm
        self.MAX_THRESHOLD = 1.8  # 1.8 meters

        # Display configuration
        self.DISPLAY_WINDOW = False       # CV2 window display flag
        self.SHOW_CONSOLE_PREVIEW = True  # Preview
        self.SHOW_STATS = True            # Statistics display flag
        self.MIRROR_MODE = True           # Mirror mode flag
        
        # Timing configuration
        self.UI_REFRESH_INTERVAL = 0.04  # how often to refresh UI (40ms)
        self.COUNTER_INCREMENT_INTERVAL = 0.5  # how often to increment counters (500ms)

        # Grid dimensions for depth analysis
        self.nH = 10  # Horizontal divisions
        self.nV = 6   # Vertical divisions