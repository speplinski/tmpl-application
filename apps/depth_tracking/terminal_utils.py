import sys
import select
import tty
import termios

class TerminalUtils:
    @staticmethod
    def is_data() -> bool:
        """Check for data on stdin."""
        return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

    @staticmethod
    def get_key() -> str:
        """Get keypress from stdin without blocking."""
        if TerminalUtils.is_data():
            return sys.stdin.read(1)
        return None

    @staticmethod
    def init_terminal():
        """Set terminal to raw mode."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
        except termios.error:
            pass
        return old_settings

    @staticmethod
    def restore_terminal(old_settings):
        """Restore terminal settings."""
        try:
            fd = sys.stdin.fileno()
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except termios.error:
            pass

    @staticmethod
    def move_cursor(x: int, y: int):
        """Move cursor position."""
        sys.stdout.write(f"\033[{y};{x}H")
        sys.stdout.flush()

    @staticmethod
    def clear_screen():
        """Clear screen."""
        sys.stdout.write("\033[2J")
        sys.stdout.flush()

    @staticmethod
    def hide_cursor():
        """Hide cursor."""
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    @staticmethod
    def show_cursor():
        """Show cursor."""
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()


class TerminalContext:
    def __init__(self, hide_cursor=True):
        self.hide_cursor = hide_cursor
        self.old_settings = None

    def __enter__(self):
        self.old_settings = TerminalUtils.init_terminal()
        if self.hide_cursor:
            TerminalUtils.hide_cursor()
        TerminalUtils.clear_screen()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.hide_cursor:
            TerminalUtils.show_cursor()
        if self.old_settings:
            TerminalUtils.restore_terminal(self.old_settings)
        TerminalUtils.clear_screen()