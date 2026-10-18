@echo off
setlocal
cd /d "%~dp0"

echo === Building PathCUT with PyInstaller ===
pyinstaller pathcut.spec --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller failed.
    exit /b 1
)

echo.
echo === Building installer with Inno Setup ===
where ISCC >nul 2>&1
if errorlevel 1 (
    echo ISCC.exe not found on PATH.
    echo Trying default install location...
    set "ISCC=I:\Inno Setup 6\ISCC.exe"
) else (
    set "ISCC=ISCC"
)

"%ISCC%" installer.iss
if errorlevel 1 (
    echo ERROR: Inno Setup compilation failed.
    exit /b 1
)

echo.
echo === Done ===
echo Installer: Output\PathCUT-Setup.exe
