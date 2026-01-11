@echo off
setlocal enabledelayedexpansion

REM ============================================
REM CatchSnapWeb v2.0 Launcher
REM ============================================

echo.
echo ============================================
echo    CatchSnapWeb v2.0 Traffic Recorder
echo ============================================
echo.

REM ============================================
REM Check Python installation
REM ============================================
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.8 or newer from https://www.python.org
    echo.
    pause
    exit /b 1
)

echo [INFO] Python found:
python --version

REM ============================================
REM Check/Create Virtual Environment
REM ============================================
if not exist "venv\Scripts\activate.bat" (
    echo.
    echo [INFO] Virtual Environment not found. Creating venv...
    python -m venv venv

    if errorlevel 1 (
        echo [ERROR] Could not create Virtual Environment!
        echo Make sure you have write permissions in this directory.
        echo.
        pause
        exit /b 1
    )

    echo [OK] Virtual Environment created successfully!
) else (
    echo [OK] Virtual Environment found.
)

REM ============================================
REM Activate Virtual Environment
REM ============================================
echo [INFO] Activating Virtual Environment...
call venv\Scripts\activate.bat

if errorlevel 1 (
    echo [ERROR] Could not activate Virtual Environment!
    pause
    exit /b 1
)

REM ============================================
REM Check requirements and install if needed
REM ============================================
echo [INFO] Checking installed packages...

REM Check critical packages
set MISSING_PACKAGES=0

python -c "import playwright" 2>nul
if errorlevel 1 (
    echo [WARNING] Playwright not installed!
    set MISSING_PACKAGES=1
)

python -c "import aiofiles" 2>nul
if errorlevel 1 (
    echo [WARNING] aiofiles not installed!
    set MISSING_PACKAGES=1
)

python -c "import rich" 2>nul
if errorlevel 1 (
    echo [WARNING] rich not installed!
    set MISSING_PACKAGES=1
)

python -c "import yaml" 2>nul
if errorlevel 1 (
    echo [WARNING] pyyaml not installed!
    set MISSING_PACKAGES=1
)

REM Install missing packages
if %MISSING_PACKAGES%==1 (
    echo.
    echo [INFO] Installing missing packages...
    echo [INFO] This may take a few minutes...
    echo.

    pip install -r requirements.txt

    if errorlevel 1 (
        echo.
        echo [ERROR] Installation failed!
        echo Try manually: pip install -r requirements.txt
        echo.
        call deactivate
        pause
        exit /b 1
    )

    echo.
    echo [OK] All packages installed successfully!
) else (
    echo [OK] All required packages are installed.
)

REM ============================================
REM Check Playwright browsers
REM ============================================
echo [INFO] Checking Playwright browsers...

python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); p.chromium.executable_path; p.stop()" 2>nul
if errorlevel 1 (
    echo.
    echo [WARNING] Playwright browsers not installed!
    echo [INFO] Installing Playwright browsers...
    echo [INFO] This may take 2-5 minutes...
    echo.

    playwright install

    if errorlevel 1 (
        echo.
        echo [ERROR] Browser installation failed!
        echo Try manually: playwright install
        echo.
        call deactivate
        pause
        exit /b 1
    )

    echo.
    echo [OK] Playwright browsers installed successfully!
) else (
    echo [OK] Playwright browsers found.
)

echo.
echo ============================================
echo [OK] Setup complete! Starting application...
echo ============================================
echo.

REM ============================================
REM Browser selection
REM ============================================
echo Choose your browser:
echo.
echo [1] Chrome (locally installed - latest version)
echo [2] Edge (locally installed - latest version)
echo [3] Brave (locally installed - latest version)
echo [4] Firefox (Playwright - Version 144.0.2)
echo [5] Chromium (Playwright - Version 143.0.7499.4)
echo [6] WebKit (Playwright - Safari Engine)
echo.
set /p choice="Enter number (1-6): "

REM Set browser based on selection
set BROWSER=chrome
set BROWSER_NAME=Chrome

if "%choice%"=="1" (
    set BROWSER=chrome
    set BROWSER_NAME=Chrome
)
if "%choice%"=="2" (
    set BROWSER=msedge
    set BROWSER_NAME=Edge
)
if "%choice%"=="3" (
    set BROWSER=brave
    set BROWSER_NAME=Brave
)
if "%choice%"=="4" (
    set BROWSER=firefox
    set BROWSER_NAME=Firefox
)
if "%choice%"=="5" (
    set BROWSER=chromium
    set BROWSER_NAME=Chromium
)
if "%choice%"=="6" (
    set BROWSER=webkit
    set BROWSER_NAME=WebKit
)

REM Check if valid selection
if not defined BROWSER_NAME (
    echo.
    echo [WARNING] Invalid selection! Using default browser: Chrome
    set BROWSER=chrome
    set BROWSER_NAME=Chrome
    timeout /t 2 >nul
)

echo.
echo ============================================
echo Selected: %BROWSER_NAME%
echo ============================================
echo.

REM ============================================
REM URL input
REM ============================================
echo Would you like to open a specific URL?
echo Default: https://www.snapchat.com/web
echo.
echo Examples:
echo   - https://www.snapchat.com/web
echo   - https://web.snapchat.com
echo.
set /p TARGET_URL="Enter URL (empty = default): "

REM URL validation (simple)
if defined TARGET_URL (
    echo %TARGET_URL% | findstr /C:"http://" /C:"https://" >nul
    if errorlevel 1 (
        echo.
        echo [WARNING] URL should start with http:// or https://!
        echo Using default URL...
        set TARGET_URL=
        timeout /t 2 >nul
    )
)

if not defined TARGET_URL (
    set TARGET_URL=https://www.snapchat.com/web
    echo Using default URL: %TARGET_URL%
)

echo.
echo ============================================
REM ============================================
REM Advanced options
REM ============================================
echo.
echo Advanced Options (Optional):
echo.
set /p SHOW_ADVANCED="Show advanced options? (y/N): "

set HEADLESS=false
set HAR_ENABLED=true
set BLOB_ENABLED=true

if /i "%SHOW_ADVANCED%"=="y" (
    echo.
    echo --- Advanced Settings ---
    echo.

    REM Headless mode
    set /p HEADLESS_INPUT="Enable headless mode? ^(Browser invisible^) (y/N): "
    if /i "!HEADLESS_INPUT!"=="y" set HEADLESS=true

    REM HAR recording
    set /p HAR_INPUT="Enable HAR recording? ^(HTTP Archive^) (Y/n): "
    if /i "!HAR_INPUT!"=="n" set HAR_ENABLED=false

    REM Blob download
    set /p BLOB_INPUT="Enable blob download? ^(Snapchat media^) (Y/n): "
    if /i "!BLOB_INPUT!"=="n" set BLOB_ENABLED=false

    echo.
)

REM ============================================
REM Show startup configuration
REM ============================================
echo.
echo ============================================
echo Startup Configuration:
echo ============================================
echo   Browser:      %BROWSER_NAME%
echo   URL:          %TARGET_URL%
echo   Headless:     %HEADLESS%
echo   HAR Export:   %HAR_ENABLED%
echo   Blob DL:      %BLOB_ENABLED% ^(Snapchat only^)
echo ============================================
echo.

REM Short pause
timeout /t 2 >nul

REM ============================================
REM Activate Virtual Environment
REM ============================================
echo Activating Virtual Environment...
call venv\Scripts\activate.bat

if errorlevel 1 (
    echo [ERROR] Could not activate Virtual Environment!
    pause
    exit /b 1
)

REM ============================================
REM Check if Playwright is installed
REM ============================================
python -c "import playwright" 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Playwright not installed!
    echo Please run: pip install -r requirements.txt
    echo.
    pause
    call deactivate
    exit /b 1
)

REM ============================================
REM Start Traffic Recorder
REM ============================================
echo.
echo Starting CatchSnapWeb v2.0...
echo.

REM Set environment variables for config override
set CATCHSNAP_BROWSER=%BROWSER%
if "%HEADLESS%"=="true" set CATCHSNAP_HEADLESS=true

REM Start Python script with parameters
python CatchSnapWeb.py %BROWSER% "%TARGET_URL%"

REM Save error code
set ERROR_CODE=%errorlevel%

REM ============================================
REM Deactivate venv
REM ============================================
call deactivate

REM ============================================
REM Completion
REM ============================================
echo.
if %ERROR_CODE% equ 0 (
    echo ============================================
    echo   Recording completed successfully!
    echo ============================================
) else (
    echo ============================================
    echo   Execution error ^(Code: %ERROR_CODE%^)
    echo ============================================
)
echo.
echo Press any key to close...
pause > nul

endlocal
