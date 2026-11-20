"""
editor.py
The editor core: screen layout, rendering, input loop and commands.
It composes terminal.py (I/O), buffer.py (text model) and syntax.py (colours).
"""

import syntax
from buffer import Buffer
from terminal import (RawMode, RESET, CLEAR, HOME, HIDE_CURSOR, SHOW_CURSOR,
                      get_size, move_cursor, read_key, write)

# --------------------------------------------------------------------------- #
# Palette
# --------------------------------------------------------------------------- #
RESET_FG = "\x1b[39m"
BOLD = "\x1b[1m"
WHITE = "\x1b[97m"

BG_TAB = "\x1b[48;5;238m"
BG_TAB_ACTIVE = "\x1b[48;5;24m"
FG_TAB_ACTIVE = "\x1b[1;97m"
FG_TAB = "\x1b[37m"
FG_TAB_SEP = "\x1b[90m"

BG_STATUS = "\x1b[48;5;24m"
FG_STATUS = "\x1b[97m"
BG_CURRENT = "\x1b[48;5;236m"
BG_SELECT = "\x1b[48;5;244m"
BG_SEARCH = "\x1b[48;5;136m"
FG_GUTTER = "\x1b[90m"
FG_GUTTER_CURRENT = "\x1b[1;33m"
FG_ERROR = "\x1b[91m"
FG_INFO = "\x1b[96m"
INVERT = "\x1b[7m"

TAB_WIDTH = 4

HELP_LINES = [
    "Micro-like Terminal Editor - key bindings",
    "",
    "  Move        Arrows          Home / End        PgUp / PgDn",
    "  Word left/right  Ctrl+Left / Ctrl+Right",
    "  Start/end        Ctrl+Home / Ctrl+End",
    "  Insert          type          Enter           Tab",
    "  Delete          Backspace     Delete",
    "  Undo / Redo     Ctrl+Z        Ctrl+Y",
    "  Select all      Ctrl+A        Copy Ctrl+C   Cut Ctrl+X   Paste Ctrl+V",
    "  Delete line     Ctrl+D",
    "  Save            Ctrl+S        Save as / Open  Ctrl+O",
    "  New / close tab Ctrl+N        Ctrl+W",
    "  Find            Ctrl+F        Next match F3",
    "  Help            F1",
    "  Quit            Ctrl+Q",
    "",
    "  Press any key to close this help.",
]


def expand_tabs(text, width=TAB_WIDTH):
    """Expand tabs into spaces using tab stops."""
    out = []
    col = 0
    for ch in text:
        if ch == "\t":
            spaces = width - (col % width)
            out.append(" " * spaces)
            col += spaces
        else:
            out.append(ch)
            col += 1
    return "".join(out)


def cells_to_string(cells):
    """Turn a list of (char, fg, bg) tuples into a styled ANSI row."""
    out = []
    cur_fg = cur_bg = None
    for ch, fg, bg in cells:
        if fg != cur_fg or bg != cur_bg:
            out.append(RESET)
            if fg:
                out.append(fg)
            if bg:
                out.append(bg)
            cur_fg, cur_bg = fg, bg
        out.append(ch)
    out.append(RESET)
    return "".join(out)


def blank_row(cols, fg=None, bg=None):
    return [(" ", fg, bg) for _ in range(cols)]


def put_text(cells, x, text, fg=None, bg=None):
    for i, ch in enumerate(text):
        if 0 <= x + i < len(cells):
            cells[x + i] = (ch, fg, bg)


class Editor:
    def __init__(self, files=None):
        self.buffers = []
        if files:
            for f in files:
                try:
                    self.buffers.append(Buffer(f))
                except OSError as e:
                    self.buffers.append(Buffer())
                    self._startup_error = "Could not open {}: {}".format(f, e)
        if not self.buffers:
            self.buffers.append(Buffer())
        self.active = 0
        self.clipboard = ""
        self.message = ""
        self.message_error = False
        self.prompt = None          # {"label","value","callback","confirm"}
        self.search_query = ""
        self.show_help = False
        self.quit_requested = False
        self.rows, self.cols = 24, 80
        self.text_height = 21
        self.gutter_width = 5
        self._startup_error = getattr(self, "_startup_error", "")

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @property
    def buffer(self):
        return self.buffers[self.active]

    def set_message(self, text, error=False):
        self.message = text
        self.message_error = error

    def start_prompt(self, label, callback, initial="", confirm=False):
        self.prompt = {
            "label": label,
            "value": initial,
            "callback": callback,
            "confirm": confirm,
        }

    def _scroll_into_view(self):
        b = self.buffer
        if b.cursor_row < b.top_line:
            b.top_line = b.cursor_row
        elif b.cursor_row >= b.top_line + self.text_height:
            b.top_line = b.cursor_row - self.text_height + 1
        b.top_line = max(0, b.top_line)

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def render(self):
        self.rows, self.cols = get_size()
        self.rows = max(self.rows, 6)
        self.cols = max(self.cols, 40)
        self.text_height = max(1, self.rows - 3)

        write(HIDE_CURSOR)
        write(CLEAR + HOME)

        for row_index in range(self.rows):
            if row_index == 0:
                cells = self._render_tab_bar()
            elif row_index == self.rows - 1:
                cells = self._render_message_bar()
            elif row_index == self.rows - 2:
                cells = self._render_status_bar()
            else:
                text_line = row_index - 1  # 0-based within text area
                if self.show_help:
                    cells = self._render_help(text_line)
                else:
                    cells = self._render_text_line(text_line)
            move_cursor(row_index + 1, 1)
            write(cells_to_string(cells))

        # Position the real cursor.
        b = self.buffer
        if self.show_help or self.prompt:
            if self.prompt:
                move_cursor(self.rows, len(self.prompt["label"]) +
                            len(self.prompt["value"]) + 2)
            else:
                move_cursor(2, 1)
        else:
            visual = expand_tabs(b.line[:b.cursor_col])
            screen_row = 2 + (b.cursor_row - b.top_line)
            screen_col = self.gutter_width + len(visual) + 1
            move_cursor(screen_row, screen_col)
        write(SHOW_CURSOR)

    def _render_tab_bar(self):
        cells = blank_row(self.cols, FG_TAB, BG_TAB)
        x = 0
        for idx, b in enumerate(self.buffers):
            active = idx == self.active
            label = ("\u25cf " if b.modified else "") + b.display_name
            seg = " " + label + " "
            put_text(cells, x, seg,
                     FG_TAB_ACTIVE if active else FG_TAB,
                     BG_TAB_ACTIVE if active else BG_TAB)
            x += len(seg)
            put_text(cells, x, "\u2502", FG_TAB_SEP, BG_TAB)
            x += 1
        put_text(cells, x, " + ", FG_TAB, BG_TAB)
        return cells

    def _render_status_bar(self):
        b = self.buffer
        cells = blank_row(self.cols, FG_STATUS, BG_STATUS)
        left = " {}  {}{}".format(
            b.display_name,
            "[Modified] " if b.modified else "",
            "UTF-8",
        )
        lang = b.filename.rsplit(".", 1)[-1].upper() if b.filename and "." in b.filename else "TEXT"
        right = "Ln {}, Col {}   {}  ".format(
            b.cursor_row + 1, b.cursor_col + 1, lang)
        put_text(cells, 0, left, FG_STATUS, BG_STATUS)
        put_text(cells, self.cols - len(right), right, FG_STATUS, BG_STATUS)
        return cells

    def _render_message_bar(self):
        cells = blank_row(self.cols)
        if self.prompt:
            p = self.prompt
            put_text(cells, 0, p["label"], FG_INFO, None)
            if p["confirm"]:
                put_text(cells, len(p["label"]), " [y/N]", FG_INFO, None)
            else:
                put_text(cells, len(p["label"]), p["value"], RESET_FG, None)
                put_text(cells, len(p["label"]) + len(p["value"]), "\u2588", INVERT, None)
        elif self.message:
            put_text(cells, 0, self.message,
                     FG_ERROR if self.message_error else FG_INFO, None)
        else:
            hint = ("Ctrl+Q Quit  Ctrl+S Save  Ctrl+O Open  Ctrl+F Find  "
                    "Ctrl+N New  Ctrl+W Close  F1 Help")
            put_text(cells, 0, hint, FG_GUTTER, None)
        return cells

    def _render_help(self, text_line):
        cells = blank_row(self.cols)
        if text_line < len(HELP_LINES):
            put_text(cells, 2, HELP_LINES[text_line], FG_INFO, None)
        return cells

    def _render_text_line(self, text_line):
        b = self.buffer
        idx = b.top_line + text_line
        num_width = len(str(len(b.lines)))
        self.gutter_width = num_width + 3

        cells = blank_row(self.cols)
        if idx >= len(b.lines):
            # empty area below end of file
            for c in range(self.gutter_width):
                cells[c] = (" ", FG_GUTTER, None)
            return cells

        line = b.lines[idx]
        expanded = expand_tabs(line)
        is_current = idx == b.cursor_row

        # map raw character index -> visual column
        raw_to_visual = []
        v = 0
        for ch in line:
            raw_to_visual.append(v)
            v += (TAB_WIDTH - (v % TAB_WIDTH)) if ch == "\t" else 1

        def col_to_visual(col):
            if col >= len(line):
                return len(expanded)
            return raw_to_visual[col]

        # syntax colours per visual column
        fg = [None] * len(expanded)
        for start, token, kind in syntax.highlight(line, b.filename):
            colour = syntax.COLOR[kind]
            for j, ch in enumerate(token):
                ri = start + j
                if ri >= len(raw_to_visual):
                    break
                vs = raw_to_visual[ri]
                vw = (TAB_WIDTH - (vs % TAB_WIDTH)) if ch == "\t" else 1
                for k in range(vs, min(vs + vw, len(expanded))):
                    fg[k] = colour

        # selection range in visual columns
        sel_vstart = sel_vend = None
        sel = b.selection_range()
        if sel:
            (sr, sc), (er, ec) = sel
            if sr <= idx <= er:
                a = sc if idx == sr else 0
                z = ec if idx == er else len(line)
                sel_vstart = col_to_visual(a)
                sel_vend = col_to_visual(z)

        # search matches in visual columns
        matches = []
        if self.search_query:
            q = self.search_query
            start = 0
            while True:
                pos = expanded.find(q, start)
                if pos == -1:
                    break
                matches.append((pos, pos + len(q)))
                start = pos + 1

        # gutter
        gutter = "{:>{w}} \u2502 ".format(idx + 1, w=num_width)
        for c, ch in enumerate(gutter):
            cells[c] = (ch,
                        FG_GUTTER_CURRENT if is_current else FG_GUTTER,
                        BG_CURRENT if is_current else None)

        # content
        for ci, ch in enumerate(expanded):
            x = self.gutter_width + ci
            if x >= self.cols:
                break
            bg = BG_CURRENT if is_current else None
            if sel_vstart is not None and sel_vstart <= ci < sel_vend:
                bg = BG_SELECT
            for ms, me in matches:
                if ms <= ci < me:
                    bg = BG_SEARCH
                    break
            cells[x] = (ch, fg[ci] or RESET_FG, bg)

        # current-line background in the empty space to the right
        if is_current:
            for x in range(self.gutter_width + len(expanded), self.cols):
                cells[x] = (" ", None, BG_CURRENT)
        return cells

    # ------------------------------------------------------------------ #
    # Input handling
    # ------------------------------------------------------------------ #
    def _handle_prompt_key(self, key):
        p = self.prompt
        callback = p["callback"]
        if p["confirm"]:
            if key in ("CHAR:y", "CHAR:Y"):
                self.prompt = None
                callback(True)
            elif key in ("ENTER", "ESC", "CHAR:n", "CHAR:N"):
                self.prompt = None
                callback(False)
            return

        if key == "ENTER":
            value = p["value"]
            self.prompt = None
            callback(value)
        elif key == "ESC":
            self.prompt = None
            callback(None)
        elif key == "BACKSPACE":
            p["value"] = p["value"][:-1]
        elif key.startswith("CHAR:"):
            p["value"] += key[5:]

    def handle_key(self, key):
        if self.prompt:
            self._handle_prompt_key(key)
            return

        if self.show_help:
            self.show_help = False
            return

        b = self.buffer

        # navigation
        if key == "UP":
            b.move(-1, 0)
        elif key == "DOWN":
            b.move(1, 0)
        elif key == "LEFT":
            b.move(0, -1)
        elif key == "RIGHT":
            b.move(0, 1)
        elif key == "HOME":
            b.move_line_start()
        elif key == "END":
            b.move_line_end()
        elif key == "CTRL_HOME":
            b.move_file_start()
        elif key == "CTRL_END":
            b.move_file_end()
        elif key == "CTRL_LEFT":
            self._word_left(b)
        elif key == "CTRL_RIGHT":
            self._word_right(b)
        elif key == "PGUP":
            b.move(-self.text_height, 0)
        elif key == "PGDN":
            b.move(self.text_height, 0)

        # editing
        elif key == "ENTER":
            b.newline()
        elif key == "TAB":
            b.insert_tab()
        elif key == "BACKSPACE":
            b.backspace()
        elif key == "DELETE":
            b.delete_at_cursor()
        elif key.startswith("CHAR:"):
            b.insert_text(key[5:])
        elif key == "CTRL_Z":
            if b.undo():
                self.set_message("Undo")
        elif key == "CTRL_Y":
            if b.redo():
                self.set_message("Redo")
        elif key == "CTRL_A":
            b.select_all()
            self.set_message("Selected all")
        elif key == "CTRL_C":
            if b.sel_anchor is not None:
                self.clipboard = b.selected_text()
                self.set_message("Copied {} char(s)".format(len(self.clipboard)))
            else:
                self.set_message("Nothing selected", error=True)
        elif key == "CTRL_X":
            if b.sel_anchor is not None:
                self.clipboard = b.selected_text()
                b.delete_selection()
                self.set_message("Cut {} char(s)".format(len(self.clipboard)))
            else:
                self.set_message("Nothing selected", error=True)
        elif key == "CTRL_V":
            if self.clipboard:
                b.insert_text(self.clipboard)
                self.set_message("Pasted")
            else:
                self.set_message("Clipboard empty", error=True)
        elif key == "CTRL_D":
            self._delete_line(b)

        # search / help
        elif key == "CTRL_F":
            self.start_prompt("Find: ", self._cb_find, initial=self.search_query)
        elif key == "F3":
            self._find_next()
        elif key == "F1":
            self.show_help = True

        # file / tabs
        elif key == "CTRL_S":
            self._save()
        elif key == "CTRL_O":
            self.start_prompt("Open: ", self._cb_open)
        elif key == "CTRL_N":
            self.buffers.append(Buffer())
            self.active = len(self.buffers) - 1
            self.set_message("New buffer")
        elif key == "CTRL_W":
            self._close_tab()
        elif key == "CTRL_Q":
            self._quit()

    @staticmethod
    def _word_left(b):
        line = b.line
        col = b.cursor_col
        while col > 0 and not line[col - 1].isalnum():
            col -= 1
        while col > 0 and line[col - 1].isalnum():
            col -= 1
        b.cursor_col = col
        b.sel_anchor = None

    @staticmethod
    def _word_right(b):
        line = b.line
        col = b.cursor_col
        n = len(line)
        while col < n and not line[col].isalnum():
            col += 1
        while col < n and line[col].isalnum():
            col += 1
        b.cursor_col = col
        b.sel_anchor = None

    def _delete_line(self, b):
        b._push_undo()
        if len(b.lines) == 1:
            b.lines = [""]
            b.cursor_col = 0
        else:
            del b.lines[b.cursor_row]
            b.cursor_row = min(b.cursor_row, len(b.lines) - 1)
            b.cursor_col = min(b.cursor_col, len(b.line))
        b.sel_anchor = None
        b.modified = True
        self.set_message("Deleted line")

    # ------------------------------------------------------------------ #
    # Commands
    # ------------------------------------------------------------------ #
    def _save(self):
        b = self.buffer
        if b.filename:
            self._do_save(b)
        else:
            self.start_prompt("Save as: ", self._cb_save_as)

    def _cb_save_as(self, value):
        if value:
            self._do_save(self.buffer, value)

    def _do_save(self, b, filename=None):
        try:
            b.save(filename)
            self.set_message("Saved {}".format(b.filename))
        except OSError as e:
            self.set_message("Save failed: {}".format(e), error=True)

    def _cb_open(self, value):
        if not value:
            return
        try:
            nb = Buffer(value)
            self.buffers.append(nb)
            self.active = len(self.buffers) - 1
            self.set_message("Opened {}".format(nb.filename))
        except OSError as e:
            self.set_message("Open failed: {}".format(e), error=True)

    def _close_tab(self):
        if self.buffer.modified:
            self.start_prompt("Unsaved changes. Close tab? [y/N]",
                              self._cb_close_confirm, confirm=True)
        else:
            self._close_active()

    def _cb_close_confirm(self, yes):
        if yes:
            self._close_active()

    def _close_active(self):
        if len(self.buffers) == 1:
            self.buffers = [Buffer()]
        else:
            del self.buffers[self.active]
            self.active = min(self.active, len(self.buffers) - 1)
        self.set_message("Closed tab")

    def _quit(self):
        if any(b.modified for b in self.buffers):
            self.start_prompt("Unsaved changes. Quit? [y/N]",
                              self._cb_quit_confirm, confirm=True)
        else:
            self.quit_requested = True

    def _cb_quit_confirm(self, yes):
        if yes:
            self.quit_requested = True

    def _cb_find(self, value):
        if not value:
            return
        self.search_query = value
        if self.buffer.find(value):
            self.set_message("Found '{}'".format(value))
        else:
            self.set_message("Not found", error=True)

    def _find_next(self):
        if not self.search_query:
            self.set_message("No search query", error=True)
            return
        if self.buffer.find(self.search_query):
            self.set_message("Found '{}'".format(self.search_query))
        else:
            self.set_message("No more matches", error=True)

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #
    def run(self):
        with RawMode():
            write(HIDE_CURSOR)
            if self._startup_error:
                self.set_message(self._startup_error, error=True)
            try:
                while not self.quit_requested:
                    self._scroll_into_view()
                    self.render()
                    key = read_key()
                    self.handle_key(key)
            finally:
                write(SHOW_CURSOR + RESET + CLEAR + HOME)
                write("Editor closed. Goodbye!\r\n")
