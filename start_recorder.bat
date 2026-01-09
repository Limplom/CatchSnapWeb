@echo off
setlocal enabledelayedexpansion

echo ============================================
echo Browser Traffic Recorder
echo ============================================
echo.
echo Waehle deinen Browser:
echo.
echo [1] Chrome (lokal installiert - neueste Version)
echo [2] Edge (lokal installiert - neueste Version)
echo [3] Brave (lokal installiert - neueste Version)
echo [4] Firefox (Playwright - Version 144.0.2)
echo [5] Chromium (Playwright - Version 143.0.7499.4)
echo [6] WebKit (Playwright - Safari Engine)
echo.
set /p choice="Gib die Nummer ein (1-6): "

REM Browser basierend auf Auswahl setzen
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

REM Prüfe ob gültige Auswahl
if not defined BROWSER (
    echo.
    echo Ungueltige Auswahl! Verwende Standard-Browser: Chrome
    set BROWSER=chrome
    set BROWSER_NAME=Chrome
    timeout /t 2 >nul
)

echo.
echo ============================================
echo Gewaehlt: %BROWSER_NAME%
echo ============================================
echo.

REM Frage nach URL
echo Moechtest du eine spezifische URL oeffnen?
echo (Leer lassen fuer Standard: https://www.snapchat.com/web)
echo.
set /p TARGET_URL="URL eingeben: "

REM Wenn keine URL angegeben, leer lassen (Script nutzt Standard)
if not defined TARGET_URL (
    echo Verwende Standard-URL: https://www.snapchat.com/web
)

echo.
echo ============================================
echo Start-Konfiguration:
echo   Browser: %BROWSER_NAME%
if defined TARGET_URL (
    echo   URL: %TARGET_URL%
) else (
    echo   URL: https://www.snapchat.com/web ^(Standard^)
)
echo ============================================
echo.

REM Aktiviere Virtual Environment
echo Aktiviere Virtual Environment...
call venv\Scripts\activate.bat

echo.
echo Starte Traffic Recorder + Blob Downloader...
echo HINWEIS: Alle Blob-URLs werden automatisch heruntergeladen!
echo.

REM Starte das Python Script mit Browser-Parameter und optionaler URL
if defined TARGET_URL (
    python traffic_recorder.py %BROWSER% "%TARGET_URL%"
) else (
    python traffic_recorder.py %BROWSER%
)

REM Deaktiviere venv wenn Script beendet wurde
call deactivate

echo.
echo Script beendet. Druecke eine Taste zum Schliessen...
pause > nul

endlocal
