import time

class PlaybackStatistics:
    """Handles playback statistics and display"""
    def __init__(self):
        self.playback_time = 0.0
        self.total_source_frames = 1
        self.total_displayed_frames = 1
        self.last_playback_start = time.time()
        self.playing = True

    def format_stats(self):
        """Format current playback statistics as a string"""
        hours, remainder = divmod(self.playback_time, 3600)
        minutes, seconds = divmod(remainder, 60)

        source_fps = self.total_source_frames / max(self.playback_time, 0.001)
        total_fps = self.total_displayed_frames / max(self.playback_time, 0.001)

        return (
            f"{int(hours):02}:{int(minutes):02}:{seconds:05.2f} | "
            f"Source frames: {self.total_source_frames} ({source_fps:.1f}/s) | "
            f"Total frames: {self.total_displayed_frames} ({total_fps:.1f}/s)"
        )

    def update_playback_time(self, current_time):
        """Update playback time if playing"""
        if self.playing:
            self.playback_time += (current_time - self.last_playback_start)
            self.last_playback_start = current_time

    def start_playback(self):
        """Start or resume playback"""
        if not self.playing:
            self.last_playback_start = time.time()
            self.playing = True

    def pause_playback(self):
        """Pause playback and update total time"""
        if self.playing:
            self.playback_time += time.time() - self.last_playback_start
            self.playing = False
