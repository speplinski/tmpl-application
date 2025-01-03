import time

class PlaybackStatistics:
    """Handles playback statistics and display"""
    def __init__(self):
        self.start_time = 0
        self.playback_time = 0.0
        self.source_frames = 0
        self.displayed_frames = 0
        self.playing = False

    def format_stats(self):
        """Format current playback statistics as a string"""
        if self.start_time == 0:
            return "00:00:00.00 | Source frames: 0 (0.0/s) | Total frames: 0 (0.0/s)"
        
        elapsed = time.time() - self.start_time
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)

        source_fps = self.source_frames / max(elapsed, 0.001)
        display_fps = self.displayed_frames / max(elapsed, 0.001)

        return (
            f"{int(hours):02}:{int(minutes):02}:{seconds:05.2f} | "
            f"Source frames: {self.source_frames} ({source_fps:.1f}/s) | "
            f"Total frames: {self.displayed_frames} ({display_fps:.1f}/s)"
        )

    def update_source_frame(self):
        """Call when new source frame arrives"""
        self.source_frames += 1

    def update_display_frame(self):
        """Call on every displayed frame (source or interpolated)"""
        self.displayed_frames += 1
       
    def start_playback(self, start_time=None):
        """Start or resume playback with optional start time"""
        if start_time is not None:
            self.start_time = start_time
        elif self.start_time == 0:
            self.start_time = time.time()
        self.playing = True

    def pause_playback(self):
        """Pause playback"""
        self.playing = False
