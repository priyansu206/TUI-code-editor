"""
buffer.py
The text buffer: holds the lines of a file, the cursor, undo/redo history,
selection state and file metadata.  Editing operations live here so the
editor layer only worries about rendering and input.
"""

import os


class Buffer:
    def __init__(self, filename=None):
        self.lines = [""]
        self.cursor_row = 0
        self.cursor_col = 0
        self.filename = filename
        self.modified = False
        self.sel_anchor = None          # (row, col) or None
        self.top_line = 0               # first visible line (scroll position)
        self._undo = []
        self._redo = []
        if filename:
            try:
                self.load(filename)
            except FileNotFoundError:
                # `bheem newfile.py` -> open a ready-to-edit empty buffer that
                # remembers the name so Ctrl+S saves straight to it.
                self.filename = os.path.abspath(filename)
                self.lines = [""]
                self.modified = False
                self.cursor_row = self.cursor_col = 0
                self.sel_anchor = None
                self.top_line = 0

    # ------------------------------------------------------------------ #
    # File I/O
    # ------------------------------------------------------------------ #
    def load(self, filename):
        with open(filename, "r", encoding="utf-8", errors="replace") as fh:
            self.lines = fh.read().replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if not self.lines:
            self.lines = [""]
        self.filename = os.path.abspath(filename)
        self.modified = False
        self.cursor_row = self.cursor_col = 0
        self.sel_anchor = None
        self.top_line = 0
        self._undo.clear()
        self._redo.clear()

    def save(self, filename=None):
        if filename:
            self.filename = os.path.abspath(filename)
        if not self.filename:
            raise ValueError("No filename set")
        with open(self.filename, "w", encoding="utf-8", newline="") as fh:
            fh.write("\n".join(self.lines))
        self.modified = False

    @property
    def display_name(self):
        return os.path.basename(self.filename) if self.filename else "[No Name]"

    # ------------------------------------------------------------------ #
    # Snapshot / history
    # ------------------------------------------------------------------ #
    def _snapshot(self):
        return (list(self.lines), self.cursor_row, self.cursor_col, self.sel_anchor)

    def _restore(self, snap):
        self.lines, self.cursor_row, self.cursor_col, self.sel_anchor = snap

    def _push_undo(self):
        self._undo.append(self._snapshot())
        if len(self._undo) > 500:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self):
        if not self._undo:
            return False
        self._redo.append(self._snapshot())
        self._restore(self._undo.pop())
        self.modified = True
        return True

    def redo(self):
        if not self._redo:
            return False
        self._undo.append(self._snapshot())
        self._restore(self._redo.pop())
        self.modified = True
        return True

    # ------------------------------------------------------------------ #
    # Cursor helpers
    # ------------------------------------------------------------------ #
    @property
    def line(self):
        return self.lines[self.cursor_row]

    def clamp_cursor(self):
        self.cursor_row = max(0, min(self.cursor_row, len(self.lines) - 1))
        self.cursor_col = max(0, min(self.cursor_col, len(self.line)))

    def move(self, drow, dcol):
        self.cursor_row += drow
        self.cursor_col += dcol
        self.clamp_cursor()
        self.sel_anchor = None

    def move_line_start(self):
        self.cursor_col = 0
        self.sel_anchor = None

    def move_line_end(self):
        self.cursor_col = len(self.line)
        self.sel_anchor = None

    def move_file_start(self):
        self.cursor_row = 0
        self.cursor_col = 0
        self.sel_anchor = None

    def move_file_end(self):
        self.cursor_row = len(self.lines) - 1
        self.cursor_col = len(self.line)
        self.sel_anchor = None

    # ------------------------------------------------------------------ #
    # Selection
    # ------------------------------------------------------------------ #
    def select_all(self):
        self.sel_anchor = (0, 0)
        self.cursor_row = len(self.lines) - 1
        self.cursor_col = len(self.line)

    def selection_range(self):
        """Return ((start_row, start_col), (end_row, end_col)) or None."""
        if self.sel_anchor is None:
            return None
        a = self.sel_anchor
        b = (self.cursor_row, self.cursor_col)
        if a <= b:
            return a, b
        return b, a

    def selected_text(self):
        rng = self.selection_range()
        if rng is None:
            return ""
        (sr, sc), (er, ec) = rng
        if sr == er:
            return self.lines[sr][sc:ec]
        parts = [self.lines[sr][sc:]]
        parts.extend(self.lines[sr + 1:er])
        parts.append(self.lines[er][:ec])
        return "\n".join(parts)

    def clear_selection(self):
        self.sel_anchor = None

    # ------------------------------------------------------------------ #
    # Editing
    # ------------------------------------------------------------------ #
    def insert_text(self, text):
        """Insert text at the cursor (replacing any selection)."""
        if not text:
            return
        self._push_undo()
        if self.sel_anchor is not None:
            self._delete_selection_raw()
        parts = text.split("\n")
        if len(parts) == 1:
            line = self.line
            self.lines[self.cursor_row] = (
                line[:self.cursor_col] + text + line[self.cursor_col:]
            )
            self.cursor_col += len(text)
        else:
            line = self.line
            before = line[:self.cursor_col]
            after = line[self.cursor_col:]
            new_lines = [before + parts[0]]
            new_lines.extend(parts[1:-1])
            new_lines.append(parts[-1] + after)
            self.lines[self.cursor_row:self.cursor_row + 1] = new_lines
            self.cursor_row += len(parts) - 1
            self.cursor_col = len(parts[-1])
        self.sel_anchor = None
        self.modified = True
        self.clamp_cursor()

    def _delete_selection_raw(self):
        rng = self.selection_range()
        if rng is None:
            return
        (sr, sc), (er, ec) = rng
        if sr == er:
            self.lines[sr] = self.lines[sr][:sc] + self.lines[sr][ec:]
        else:
            self.lines[sr] = self.lines[sr][:sc] + self.lines[er][ec:]
            del self.lines[sr + 1:er + 1]
        self.cursor_row, self.cursor_col = sr, sc
        self.sel_anchor = None
        self.clamp_cursor()

    def delete_selection(self):
        if self.sel_anchor is None:
            return
        self._push_undo()
        self._delete_selection_raw()
        self.modified = True

    def backspace(self):
        if self.sel_anchor is not None:
            self.delete_selection()
            return
        if self.cursor_col > 0:
            self._push_undo()
            line = self.line
            self.lines[self.cursor_row] = (
                line[:self.cursor_col - 1] + line[self.cursor_col:]
            )
            self.cursor_col -= 1
            self.modified = True
        elif self.cursor_row > 0:
            self._push_undo()
            prev_len = len(self.lines[self.cursor_row - 1])
            self.lines[self.cursor_row - 1] += self.lines[self.cursor_row]
            del self.lines[self.cursor_row]
            self.cursor_row -= 1
            self.cursor_col = prev_len
            self.modified = True

    def delete_at_cursor(self):
        if self.sel_anchor is not None:
            self.delete_selection()
            return
        line = self.line
        if self.cursor_col < len(line):
            self._push_undo()
            self.lines[self.cursor_row] = (
                line[:self.cursor_col] + line[self.cursor_col + 1:]
            )
            self.modified = True
        elif self.cursor_row < len(self.lines) - 1:
            self._push_undo()
            self.lines[self.cursor_row] += self.lines[self.cursor_row + 1]
            del self.lines[self.cursor_row + 1]
            self.modified = True

    def newline(self):
        self.insert_text("\n")

    def insert_tab(self, width=4):
        self.insert_text(" " * width)

    # ------------------------------------------------------------------ #
    # Find
    # ------------------------------------------------------------------ #
    def find(self, query, start_row=None, start_col=None):
        """Find next occurrence after the given position; wrap around."""
        if not query:
            return False
        if start_row is None:
            start_row, start_col = self.cursor_row, self.cursor_col
        n = len(self.lines)
        for offset in range(n):
            row = (start_row + offset) % n
            line = self.lines[row]
            search_from = start_col + 1 if offset == 0 else 0
            idx = line.find(query, search_from)
            if idx != -1:
                self.cursor_row, self.cursor_col = row, idx
                self.sel_anchor = None
                return True
        return False
