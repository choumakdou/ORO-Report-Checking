@echo off
REM ──────────────────────────────────────────────────────────────────────────
REM  build_exe.bat  —  ORO QC Checker v2
REM  Run on any machine that has Python + PyInstaller installed.
REM  Output:  dist\ORO_QC_Checker\ORO_QC_Checker.exe
REM ──────────────────────────────────────────────────────────────────────────
echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo Building .exe ...
pyinstaller ^
  --name ORO_QC_Checker ^
  --onedir ^
  --windowed ^
  --icon NONE ^
  --collect-all customtkinter ^
  --collect-all fitz ^
  --collect-all reportlab ^
  --hidden-import openai ^
  --hidden-import requests ^
  --hidden-import PIL._tkinter_finder ^
  main.py

echo.
echo Build complete.  Output: dist\ORO_QC_Checker\ORO_QC_Checker.exe
echo Copy config.json (with your OpenAI API key) into the same folder as the .exe
pause
