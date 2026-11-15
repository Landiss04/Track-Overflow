@echo off
rem Numbered menu for the hardware Pi tests. Double-click it, or run it from any folder.
rem It works from the repository root, writes results to ..\trains_pi (override: set PI_TEST_OUT=folder)
rem and keeps every run's text output beside its CSV. It changes no repository file.
rem Step-by-step install guides: documents\pi_hw_results\guide-track-controller-pi.md and guide-train-controller-pi.md
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0.." || (echo Cannot find the repository root. & pause & exit /b 1)
if not defined PI_TEST_OUT set "PI_TEST_OUT=..\trains_pi"
if not exist "%PI_TEST_OUT%" mkdir "%PI_TEST_OUT%"
set "SCHED=utils\schedule_stress.json"
set "TRACK_REC=%PI_TEST_OUT%\track-red-180s.jsonl"
set "TRAIN_REC=%PI_TEST_OUT%\train-red-600s.jsonl"
where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH. Open the terminal that runs the project and start this again.
    pause
    exit /b 1
)

:menu
cls
echo ==================================================================
echo   Hardware Pi tests        results in %PI_TEST_OUT%
echo ==================================================================
echo    1  List the USB Pis (found or missing)
echo    2  HELLO to the Track Pi
echo    3  HELLO to the Train Pi
echo    4  Replay on the link, Track Pi, 180 s
echo    5  Replay on the link, Train Pi, 600 s
echo    6  System at 10x, all simulated, 60 s
echo    7  System at 10x, all simulated, 600 s   (baseline)
echo    8  System at 10x, Track Pi real, 60 s
echo    9  System at 10x, Track Pi real, 600 s
echo   10  System at 10x, Train Pi real, 60 s
echo   11  System at 10x, Train Pi real, 600 s
echo   12  Summarise the latest run (tickstats)
echo   13  Estimate both Pis real (latest two 600 s runs)
echo   14  Print the checklist for a measured run
echo    0  Quit
echo.
set "CHOICE="
set /p "CHOICE=Choose a number: "
if "%CHOICE%"=="0" goto :end
if "%CHOICE%"=="1" call :list_pis & goto :again
if "%CHOICE%"=="2" call :hello track-controller-hw track & goto :again
if "%CHOICE%"=="3" call :hello train-controller-hw train & goto :again
if "%CHOICE%"=="4" call :replay track-controller-hw track "%TRACK_REC%" 300 & goto :again
if "%CHOICE%"=="5" call :replay train-controller-hw train "%TRAIN_REC%" 700 & goto :again
if "%CHOICE%"=="6" call :system sim 60 & goto :again
if "%CHOICE%"=="7" call :system sim 600 & goto :again
if "%CHOICE%"=="8" call :system track-physical 60 & goto :again
if "%CHOICE%"=="9" call :system track-physical 600 & goto :again
if "%CHOICE%"=="10" call :system train-physical 60 & goto :again
if "%CHOICE%"=="11" call :system train-physical 600 & goto :again
if "%CHOICE%"=="12" call :summarise & goto :again
if "%CHOICE%"=="13" call :estimate & goto :again
if "%CHOICE%"=="14" call :checklist & goto :again
echo Not a menu number.
:again
echo.
pause
goto :menu

:end
endlocal
exit /b 0

rem ------------------------------------------------------------------

:stamp
rem Sets STAMP to yyyyMMdd-HHmmss.
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%T"
goto :eof

:list_pis
powershell -NoProfile -Command "python -m common.hw_link.bringup --list | ConvertFrom-Json | ForEach-Object { $_.modules.PSObject.Properties } | ForEach-Object { '{0,-22} {1,-8} {2}' -f $_.Name, $_.Value.status, ($_.Value.ports -join ',') }"
goto :eof

:need_pi
rem :need_pi module  -> errorlevel 1 when that Pi is not found on USB.
powershell -NoProfile -Command "$s = (python -m common.hw_link.bringup --list | ConvertFrom-Json).modules.'%~1'.status; if ($s -ne 'found') { exit 1 }"
if errorlevel 1 (
    echo.
    echo The %~1 Pi is not found on USB. Nothing was started. Option 1 shows what is connected.
    exit /b 1
)
exit /b 0

:precheck
rem Stops early when a Python from an earlier run is still alive, and reminds about the clipboard.
tasklist /fi "imagename eq python.exe" 2>nul | find /i "python.exe" >nul
if not errorlevel 1 (
    echo.
    echo WARNING: python.exe is already running. A leftover run holds the Pi's port and slows this one.
    echo To stop every Python on this PC use:  Get-Process python ^| Stop-Process -Force
    set "ANS="
    set /p "ANS=Start anyway? (y/N) "
    if /i not "!ANS!"=="y" exit /b 1
)
echo.
echo Before you start: clipboard history OFF, copy nothing until the run ends, other programs closed.
echo For a run with a real Pi, restart its agent with a fresh journal first (option 14 lists the lines).
echo A run that begins with "qt.qpa.mime ... clipboard" lines is disturbed: repeat it.
echo Press any key to start, or Ctrl+C to cancel.
pause >nul
exit /b 0

:hello
rem :hello module tag
call :stamp
call :need_pi %~1 || goto :eof
powershell -NoProfile -Command "python -m common.hw_link.bringup --module %~1 --timeout 20 --output '%PI_TEST_OUT%\%~2-hello-%STAMP%.json'"
echo Expect "error": null in the result above. Saved %PI_TEST_OUT%\%~2-hello-%STAMP%.json
goto :eof

:replay
rem :replay module tag recording timeout_s
if not exist "%~3" (
    echo The recording %~3 is not there. Put it in %PI_TEST_OUT% or edit the names at the top of this file.
    goto :eof
)
call :need_pi %~1 || goto :eof
call :precheck || goto :eof
call :stamp
set "BASE=%PI_TEST_OUT%\replay-%~2-%STAMP%"
powershell -NoProfile -Command "python -m common.hw_link.bringup --module %~1 --recording '%~3' --hz 100 --timeout %~4 --output '!BASE!.json' 2>&1 | Tee-Object -FilePath '!BASE!.txt'"
echo.
echo Saved !BASE!.json and !BASE!.txt
echo Look for "error": null, rtt_over_10ms and lines_lost. Pi side: see option 14.
goto :eof

:system
rem :system sim|track-physical|train-physical seconds
set "MODES="
if /i "%~1"=="sim" set "MODES=--test-pi process"
if /i "%~1"=="track-physical" (
    set "MODES=--track-controller-pi physical --train-controller-pi process"
    call :need_pi track-controller-hw || goto :eof
)
if /i "%~1"=="train-physical" (
    set "MODES=--track-controller-pi process --train-controller-pi physical"
    call :need_pi train-controller-hw || goto :eof
)
if not defined MODES (
    echo Internal error: unknown mode %~1
    goto :eof
)
call :precheck || goto :eof
call :stamp
set "BASE=%PI_TEST_OUT%\tick-%~1-%~2s-%STAMP%"
echo Running %~2 s at 10x, %~1. Do not touch the PC.
powershell -NoProfile -Command "python bench\per_module.py --system !MODES! --schedule %SCHED% --seconds %~2 --per-tick-csv '!BASE!.csv' 2>&1 | Tee-Object -FilePath '!BASE!.txt'"
echo.
echo Saved !BASE!.csv and !BASE!.txt
echo Check "speed achieved" and "ticks slipped" above; option 12 gives the detail.
echo If the clock never left 05:00:00, a Pi that was not connected was still set to real. Stop with option 14's command.
goto :eof

:summarise
set "LAST="
for /f "delims=" %%F in ('dir /b /o-d "%PI_TEST_OUT%\tick-*.csv" 2^>nul') do if not defined LAST set "LAST=%%F"
if not defined LAST (
    echo No tick-*.csv in %PI_TEST_OUT% yet. Run one of the system tests first.
    goto :eof
)
echo Latest run: !LAST!
python bench\tickstats.py "%PI_TEST_OUT%\!LAST!"
goto :eof

:estimate
set "LAST_TRACK="
set "LAST_TRAIN="
for /f "delims=" %%F in ('dir /b /o-d "%PI_TEST_OUT%\tick-track-physical-600s-*.csv" 2^>nul') do if not defined LAST_TRACK set "LAST_TRACK=%%F"
for /f "delims=" %%F in ('dir /b /o-d "%PI_TEST_OUT%\tick-train-physical-600s-*.csv" 2^>nul') do if not defined LAST_TRAIN set "LAST_TRAIN=%%F"
if not defined LAST_TRACK (
    echo No 600 s Track-Pi-real run yet. Run option 9 first.
    goto :eof
)
if not defined LAST_TRAIN (
    echo No 600 s Train-Pi-real run yet. Swap the board to the Train Controller and run option 11 first.
    goto :eof
)
echo Track run: !LAST_TRACK!
echo Train run: !LAST_TRAIN!
python bench\estimate_both.py --train-physical "%PI_TEST_OUT%\!LAST_TRAIN!" --track-physical "%PI_TEST_OUT%\!LAST_TRACK!"
echo This is an estimate from two runs taken apart, not a measurement of both Pis together.
goto :eof

:checklist
echo.
echo BEFORE A RUN WITH A REAL PI
echo   On the Pi, one line at a time:
echo     sudo systemctl stop track-overflow-agent
echo     sudo mkdir -p /var/lib/track-overflow/old-run
echo     sudo sh -c 'mv /var/lib/track-overflow/session.json* /var/lib/track-overflow/agent.log /var/lib/track-overflow/old-run/ 2^>/dev/null'
echo     sudo systemctl start track-overflow-agent
echo     pgrep -af "hw_link.agent^|agent.py"        (exactly ONE line, with the module you are testing)
echo   On this PC:
echo     python -c "from common.hw_link import agent; print(agent.AGENT_HASH[:8])"   (must equal the Pi's hash)
echo     Clipboard history off. Copy nothing during the run. Other programs closed.
echo.
echo AFTER A RUN, ON THE PI
echo     grep -c SLOW_STEP /var/lib/track-overflow/agent.log
echo     vcgencmd get_throttled        (0x0 is clean)
echo.
echo TO STOP A STUCK RUN (stops every Python on this PC)
echo     Get-Process python ^| Stop-Process -Force
echo.
echo Guides: documents\pi_hw_results\guide-track-controller-pi.md and guide-train-controller-pi.md
goto :eof
