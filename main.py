"""
main.py
Entry point for the terminal-editor.

Run:
    python main.py                start with an empty buffer
    python main.py file.py        open a file (repeat for more tabs)
    bheem file.py                 same thing, from anywhere on PATH
"""

import sys

from editor import Editor

USAGE = """bheem - terminal-editor
Usage:
  bheem                 open an empty buffer
  bheem file.txt        open a file (repeat for more tabs)
  bheem --help          show this help
"""


def main(argv):
    if any(a in ("-h", "--help", "/?") for a in argv):
        print(USAGE)
        return 0
    if "--version" in argv:
        print("bheem 1.0")
        return 0
    Editor(argv).run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
