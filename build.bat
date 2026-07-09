@echo off
chcp 65001 >nul
title Build - Outlook Image Slicer Stable
color 0A

echo.
echo ============================================
echo   Outlook Image Slicer Stable - Build Tool
echo ============================================
echo.

cd /d "%~dp0"

echo Starting build process...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"

if errorlevel 1 (
    echo.
    echo ============================================
    echo   BUILD FAILED
    echo ============================================
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   BUILD SUCCESS!
echo ============================================
echo.
echo Output: dist\OutlookImgSlicer-V6.1.1.exe
echo.
pause
