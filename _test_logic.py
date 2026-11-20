from buffer import Buffer
import syntax
import editor

b = Buffer()
b.insert_text("hello")
b.newline()
b.insert_text("world")
assert b.lines == ["hello", "world"], b.lines
assert (b.cursor_row, b.cursor_col) == (1, 5)

b.move_file_start()
b.insert_text("X")
assert b.lines == ["Xhello", "world"], b.lines

b.undo()
assert b.lines == ["hello", "world"], b.lines
b.redo()
assert b.lines == ["Xhello", "world"], b.lines

b.select_all()
txt = b.selected_text()
assert txt == "Xhello\nworld", repr(txt)
b.delete_selection()
assert b.lines == [""], b.lines

# find
b.lines = ["abc", "defabc"]
b.cursor_row = b.cursor_col = 0
# search starts after the cursor: first hit is on line 2, then wraps to line 1
assert b.find("abc") and (b.cursor_row, b.cursor_col) == (1, 3)
assert b.find("abc") and (b.cursor_row, b.cursor_col) == (0, 0)

# syntax
p = syntax.highlight("def foo(x):  # hi", "x.py")
assert any(k == "keyword" for _, _, k in p), p
assert any(k == "comment" for _, _, k in p), p
assert editor.expand_tabs("a\tb", 4) == "a   b"

# save / load round trip
import tempfile, os
path = os.path.join(tempfile.gettempdir(), "te_roundtrip_test.txt")
b2 = Buffer()
b2.insert_text("line one\nline two")
b2.save(path)
b3 = Buffer(path)
assert b3.lines == ["line one", "line two"], b3.lines
os.remove(path)

print("ALL LOGIC TESTS PASSED")
