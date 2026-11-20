"""
terminal.py
Low-level terminal handling for the terminal-editor.

Provides:
  * raw mode (no line buffering / echo) with automatic restore
  * ANSI escape-code output helpers
  * terminal size queries
  * a cross-platform read_key() that normalises keystrokes into strings

Returned key names:
  UP DOWN LEFT RIGHT HOME END PGUP PGDN DELETE INSERT
  CTRL_HOME CTRL_END CTRL_LEFT CTRL_RIGHT
  F1 .. F12
  ENTER TAB BACKSPACE ESC
  CTRL_A .. CTRL_Z
  CHAR:<character>       (for printable characters, including space)
"""

import os
import sys

IS_WINDOWS = os.name == "nt"

# --------------------------------------------------------------------------- #
# ANSI helpers
# --------------------------------------------------------------------------- #
RESET = "\x1b[0m"
CLEAR = "\x1b[2J"
HOME = "\x1b[H"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"


def write(text):
    sys.stdout.write(text)
    sys.stdout.flush()


def move_cursor(row, col):
    """Move cursor to 1-based row and col."""
    write("\x1b[{};{}H".format(row, col))


def get_size():
    """Return (rows, columns) of the terminal."""
    try:
        size = os.get_terminal_size()
        return size.lines, size.columns
    except OSError:
        return 24, 80


# --------------------------------------------------------------------------- #
# Raw mode
# --------------------------------------------------------------------------- #
class RawMode:
    """Context manager that enables raw mode and restores the terminal on exit."""

    def __init__(self):
        self._saved = None
        self._fd = None
        self._out_mode = None
        self._saved_out = None

    def __enter__(self):
        if IS_WINDOWS:
            self._enter_windows()
        else:
            self._enter_unix()
        return self

    def __exit__(self, exc_type, exc, tb):
        if IS_WINDOWS:
            self._restore_windows()
        else:
            self._restore_unix()
        return False

    # -- Windows ---------------------------------------------------------- #
    def _enter_windows(self):
        import ctypes

        self._kernel32 = ctypes.windll.kernel32
        self._stdin_handle = self._kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        self._stdout_handle = self._kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE

        mode = ctypes.c_uint32()
        self._kernel32.GetConsoleMode(self._stdin_handle, ctypes.byref(mode))
        self._saved = mode.value

        # Disable line input, echo and processed input (Ctrl+C etc.).
        raw = mode.value
        raw &= ~0x0002  # ENABLE_LINE_INPUT
        raw &= ~0x0004  # ENABLE_ECHO_INPUT
        raw &= ~0x0001  # ENABLE_PROCESSED_INPUT
        self._kernel32.SetConsoleMode(self._stdin_handle, raw)

        # Enable ANSI/VT sequence processing on output.
        out_mode = ctypes.c_uint32()
        self._kernel32.GetConsoleMode(self._stdout_handle, ctypes.byref(out_mode))
        self._saved_out = out_mode.value
        self._out_mode = self._saved_out | 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        self._kernel32.SetConsoleMode(self._stdout_handle, self._out_mode)

    def _restore_windows(self):
        self._kernel32.SetConsoleMode(self._stdin_handle, self._saved)
        self._kernel32.SetConsoleMode(self._stdout_handle, self._saved_out)

    # -- Unix ------------------------------------------------------------- #
    def _enter_unix(self):
        import termios
        import tty

        self._fd = sys.stdin.fileno()
        self._saved = termios.tcgetattr(self._fd)
        attrs = termios.tcgetattr(self._fd)
        attrs[3] &= ~(termios.ECHO | termios.ICANON | termios.ISIG | termios.IEXTEN)
        attrs[0] &= ~(termios.IXON | termios.IXOFF | termios.ICRNL | termios.INLCR)
        attrs[6][termios.VMIN] = 1
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(self._fd, termios.TCSADRAIN, attrs)

    def _restore_unix(self):
        import termios

        termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)


# --------------------------------------------------------------------------- #
# Key decoding
# --------------------------------------------------------------------------- #
_WIN_SPECIAL = {
    "H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT",
    "G": "HOME", "O": "END", "I": "PGUP", "Q": "PGDN",
    "S": "DELETE", "R": "INSERT",
}

_WIN_EXTENDED = {
    "V": "CTRL_HOME", "X": "CTRL_END",
    "s": "CTRL_LEFT", "t": "CTRL_RIGHT",
}

_WIN_FUNCTION = {
    ";": "F1", "<": "F2", "=": "F3", ">": "F4",
    "?": "F5", "@": "F6", "A": "F7", "B": "F8",
    "C": "F9", "D": "F10",
}


def _read_one_byte():
    if IS_WINDOWS:
        import msvcrt

        return msvcrt.getwch()
    return os.read(sys.stdin.fileno(), 1).decode("utf-8", "replace")


def read_key():
    """Block until a key is pressed and return a normalised key string."""
    ch = _read_one_byte()

    if IS_WINDOWS:
        if ch in ("\x00", "\xe0"):
            nxt = _read_one_byte()
            if ch == "\xe0":
                if nxt in _WIN_SPECIAL:
                    return _WIN_SPECIAL[nxt]
                if nxt in _WIN_EXTENDED:
                    return _WIN_EXTENDED[nxt]
            else:  # 0x00 prefix -> function keys
                if nxt in _WIN_FUNCTION:
                    return _WIN_FUNCTION[nxt]
            return "UNKNOWN"

        code = ord(ch)
        if code in (13, 10):
            return "ENTER"
        if code == 9:
            return "TAB"
        if code in (8, 127):
            return "BACKSPACE"
        if code == 27:
            return "ESC"
        if 1 <= code <= 26:
            return "CTRL_" + chr(code + 64)
        return "CHAR:" + ch

    # ---- Unix ----
    if ch == "\x1b":
        import select

        seq = ""
        if select.select([sys.stdin], [], [], 0.05)[0]:
            seq += os.read(sys.stdin.fileno(), 1).decode("utf-8", "replace")
        if seq == "[" or seq == "O":
            if select.select([sys.stdin], [], [], 0.05)[0]:
                seq += os.read(sys.stdin.fileno(), 1).decode("utf-8", "replace")
        escape_map = {
            "[A": "UP", "[B": "DOWN", "[C": "RIGHT", "[D": "LEFT",
            "[H": "HOME", "[F": "END", "OA": "UP", "OB": "DOWN",
            "OC": "RIGHT", "OD": "LEFT", "OH": "HOME", "OF": "END",
            "[1~": "HOME", "[4~": "END", "[5~": "PGUP", "[6~": "PGDN",
            "[3~": "DELETE", "[2~": "INSERT",
        }
        # consume any remaining bytes of a numeric sequence
        while seq.endswith("[") or (seq.startswith("[") and seq[-1].isdigit()
                                     and select.select([sys.stdin], [], [], 0)[0]):
            seq += os.read(sys.stdin.fileno(), 1).decode("utf-8", "replace")
        return escape_map.get(seq, "ESC")

    code = ord(ch)
    if code in (13, 10):
        return "ENTER"
    if code == 9:
        return "TAB"
    if code in (8, 127):
        return "BACKSPACE"
    if 1 <= code <= 26:
        return "CTRL_" + chr(code + 64)
    return "CHAR:" + ch
