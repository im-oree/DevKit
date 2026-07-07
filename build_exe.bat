@echo off
REM Build DevKit as a single .exe (Windows)
REM Requires: pip install pyinstaller

echo Building DevKit.exe...
pyinstaller --onefile --noconsole --name DevKit ^
  --add-data "devkit_core;devkit_core" ^
  --add-data "examples;examples" ^
  devkit.py

echo.
if exist "dist\DevKit.exe" (
    echo Build successful! Executable is at:  dist\DevKit.exe
    echo Copy it into any project folder and double-click to launch.
) else (
    echo Build failed. Check output above.
)
pause
