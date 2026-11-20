"""Headless render smoke test: stub out terminal I/O and exercise render()."""
import contextlib
import editor


class DummyRaw:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


captured = []
editor.get_size = lambda: (24, 80)
editor.write = lambda s: captured.append(s)
editor.move_cursor = lambda r, c: None
editor.RawMode = DummyRaw
editor.read_key = lambda: "CTRL_Q"

# Build an editor with content, selection, search matches and a tab.
e = editor.Editor()
b = e.buffer
b.filename = "example.py"
b.lines = [
    'def greet(name):  # say hello',
    '    print("Hello, " + name)',
    '',
    'greet("world")',
]
b.cursor_row = 1
b.cursor_col = 10
b.top_line = 0
b.sel_anchor = (1, 4)
b.cursor_row, b.cursor_col = 1, 14
e.search_query = "Hello"
e.set_message("a message")
e.render()

import re
raw = "".join(captured)
plain = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", raw)
assert "greet" in plain, "syntax content missing"
assert "example.py" in plain, "filename missing"
assert "Ln 2, Col 15" in plain, "status position missing: " + plain[-500:]
assert "\x1b[" in raw, "no ANSI codes emitted"

# prompt rendering
captured.clear()
e.prompt = {"label": "Save as: ", "value": "foo.py",
            "callback": lambda v: None, "confirm": False}
e.render()
assert "Save as: foo.py" in re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", "".join(captured))

# help overlay
captured.clear()
e.prompt = None
e.show_help = True
e.render()
assert "key bindings" in re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", "".join(captured))

# full run loop should terminate on CTRL_Q
editor.read_key = lambda: "CTRL_Q"
e2 = editor.Editor()
e2.run()

print("ALL RENDER TESTS PASSED")
