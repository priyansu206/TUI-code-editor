# terminal-editor

A small **Micro-style terminal code editor** written from scratch in pure
Python — no third-party dependencies. It uses raw ANSI terminal control, so
it runs in Windows Terminal, the modern PowerShell console, or any Unix-like
terminal.

## Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point |
| `editor.py` | Screen layout, rendering, input loop and commands |
| `buffer.py` | Text buffer, cursor, selection and undo/redo |
| `syntax.py` | Lightweight syntax highlighting |
| `terminal.py` | Raw mode, key decoding and terminal helpers |

## Run

From **any** terminal / directory, use the `bheem` command:

```bat
bheem                    start with an empty buffer
bheem notes.txt          open a file (creates it if it doesn't exist)
bheem notes.txt code.py  open several files, one per tab
bheem --help             show usage
```

You can also run it directly from the project folder:

```bat
cd C:\Users\priyansu\terminal-editor
python main.py
```

**How `bheem` works:** `bheem.bat` is a tiny launcher that runs
`python "...\terminal-editor\main.py" %*`. It lives in
`C:\Users\priyansu\terminal-editor` (added to your user PATH) with a copy in
`C:\Users\priyansu\.opencode\bin` so it is available immediately. Any arguments
you pass are forwarded to the editor, which opens each file as a tab. A file
that does not exist yet opens as a named empty buffer — press `Ctrl+S` to
create it.

> **Tip:** use Windows Terminal or the new PowerShell console for full colour
> and arrow-key support.

## Key bindings

| Action | Keys |
|--------|------|
| Move cursor | Arrow keys |
| Start / end of line | Home / End |
| Start / end of file | Ctrl+Home / Ctrl+End |
| Word left / right | Ctrl+Left / Ctrl+Right |
| Page up / down | PgUp / PgDn |
| Insert | Type, `Enter`, `Tab` |
| Delete | `Backspace`, `Delete`, `Ctrl+D` (delete line) |
| Undo / Redo | `Ctrl+Z` / `Ctrl+Y` |
| Select all | `Ctrl+A` |
| Copy / Cut / Paste | `Ctrl+C` / `Ctrl+X` / `Ctrl+V` |
| Save | `Ctrl+S` (Save as when unnamed) |
| Open file | `Ctrl+O` |
| New / close tab | `Ctrl+N` / `Ctrl+W` |
| Find / next match | `Ctrl+F` / `F3` |
| Help overlay | `F1` |
| Quit | `Ctrl+Q` |

Copy/cut/paste use an internal clipboard (shared between tabs).

## Features

- Multiple tabs with a tab bar and modified indicators
- Line numbers, current-line highlighting and scroll position
- Syntax highlighting for common languages (Python, JS, C/C++, Go, Rust, …)
- Selection, undo/redo, find with match highlighting
- Status bar with filename, modified state and cursor position
- Save / open prompts and unsaved-changes confirmation on close/quit

## Notes

- It is intentionally a learning/demo editor, not a replacement for Micro or
  Vim. It does not implement UTF-8 grapheme clustering, mouse support or LSP.
- The `CHAR:`-based input works for ASCII; wide/CJK characters may occupy two
  terminal cells but are tracked as one.
