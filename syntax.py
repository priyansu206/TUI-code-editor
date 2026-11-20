"""
syntax.py
A tiny, dependency-free syntax highlighter.  Each visible line is tokenised
with a regular expression and every token is paired with a colour name plus
its start offset in the raw line (needed by the renderer to handle tabs).
"""

import re

# ANSI colours
RESET = "\x1b[0m"
COLOR = {
    "plain": "\x1b[39m",
    "keyword": "\x1b[1;35m",   # bold magenta
    "string": "\x1b[32m",      # green
    "comment": "\x1b[90m",     # bright black / grey
    "number": "\x1b[33m",      # yellow
    "builtin": "\x1b[36m",     # cyan
    "func": "\x1b[94m",        # bright blue
}

COMMON_KEYWORDS = {
    "if", "else", "elif", "for", "while", "return", "break", "continue",
    "def", "class", "import", "from", "as", "in", "is", "not", "and", "or",
    "True", "False", "None", "null", "true", "false", "let", "const", "var",
    "function", "async", "await", "new", "this", "try", "catch",
    "finally", "throw", "switch", "case", "default", "do", "typeof",
    "public", "private", "protected", "static", "void", "int", "float",
    "double", "char", "bool", "struct", "enum", "typedef", "package",
    "interface", "go", "defer", "range", "func", "type", "map", "chan",
    "with", "yield", "lambda", "pass", "raise", "except", "global",
    "nonlocal", "assert", "del", "match",
}

BUILTINS = {
    "print", "len", "range", "str", "int", "float", "list", "dict", "set",
    "tuple", "open", "self", "super", "console", "Math", "Object", "Array",
    "fmt", "make", "append", "cap", "copy", "delete", "printf", "println",
    "string", "error", "nil", "input", "enumerate", "zip",
}

COMMENT_PREFIX = {
    ".py": ("#",), ".sh": ("#",), ".rb": ("#",), ".yml": ("#",),
    ".yaml": ("#",), ".toml": ("#",), ".ini": (";", "#"),
    ".js": ("//",), ".ts": ("//",), ".jsx": ("//",), ".tsx": ("//",),
    ".java": ("//",), ".c": ("//",), ".h": ("//",), ".cpp": ("//",),
    ".hpp": ("//",), ".cs": ("//",), ".go": ("//",), ".rs": ("//",),
    ".php": ("//", "#"), ".swift": ("//",), ".kt": ("//",),
    ".sql": ("--",), ".lua": ("--",), ".vim": ('"',),
    ".css": ("/*",), ".html": ("<!--",),
}

TOKEN_RE = re.compile(
    r'(?P<string>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`)'
    r'|(?P<number>\b\d+(?:\.\d+)?\b)'
    r'|(?P<ident>[A-Za-z_][A-Za-z0-9_]*)'
)


def _language(filename):
    if not filename:
        return ""
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def _comment_start(line, comments):
    """Index where a comment begins, ignoring markers inside string literals."""
    quote = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            continue
        for prefix in comments:
            if line.startswith(prefix, i):
                return i
        i += 1
    return None


def highlight(line, filename):
    """Return a list of (start_offset, text, colour_name) tuples."""
    lang = _language(filename)
    comments = COMMENT_PREFIX.get(lang, ("#", "//", ";", "--"))

    cut = _comment_start(line, comments)
    code = line if cut is None else line[:cut]
    comment = "" if cut is None else line[cut:]

    stripped = code.lstrip()
    if not stripped and comment:
        return [(0, line, "comment")]

    pieces = []
    pos = 0
    for m in TOKEN_RE.finditer(code):
        if m.start() > pos:
            pieces.append((pos, code[pos:m.start()], "plain"))
        token = m.group(0)
        if m.lastgroup == "string":
            kind = "string"
        elif m.lastgroup == "number":
            kind = "number"
        elif code[m.end():].lstrip().startswith("("):
            kind = "func"
        elif token in COMMON_KEYWORDS:
            kind = "keyword"
        elif token in BUILTINS:
            kind = "builtin"
        else:
            kind = "plain"
        pieces.append((m.start(), token, kind))
        pos = m.end()
    if pos < len(code):
        pieces.append((pos, code[pos:], "plain"))

    if comment:
        pieces.append((cut, comment, "comment"))

    return pieces or [(0, line, "plain")]
