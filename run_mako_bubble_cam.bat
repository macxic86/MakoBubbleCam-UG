@echo off
title MakoBubbleCam-UG

echo Starting MakoBubbleCam-UG...
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Please install Python and add it to PATH.
    pause
    exit /b
)

python src\mako_bubble_cam\mako_lab_interface.py

echo.
echo Program closed.
pause
