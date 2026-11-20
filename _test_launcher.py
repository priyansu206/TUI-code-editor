"""Verify file-argument behaviour used by the `bheem` launcher."""
import os
import tempfile

from editor import Editor

# existing file -> loaded into a tab
existing = os.path.join(tempfile.gettempdir(), "bheem_existing.txt")
with open(existing, "w", encoding="utf-8") as fh:
    fh.write("alpha\nbeta")

e = Editor([existing])
assert len(e.buffers) == 1
assert e.buffer.lines == ["alpha", "beta"], e.buffer.lines
assert e.buffer.filename == os.path.abspath(existing)
os.remove(existing)

# non-existent file -> empty buffer that remembers the name
missing = os.path.join(tempfile.gettempdir(), "bheem_new_file.py")
e2 = Editor([missing])
assert e2.buffer.lines == [""]
assert e2.buffer.filename == os.path.abspath(missing)
assert e2.buffer.modified is False

# multiple files -> multiple tabs
e3 = Editor([missing, existing])
assert len(e3.buffers) == 2

print("LAUNCHER BEHAVIOUR TESTS PASSED")
