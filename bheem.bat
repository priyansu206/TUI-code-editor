@echo off
rem bheem launcher: run the terminal editor with any arguments.
rem %~dp0 is this batch file's folder, so this works from any directory.
python "%~dp0main.py" %*
