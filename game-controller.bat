@echo off
cls

goto :DOES_PYTHON_EXIST

:DOES_PYTHON_EXIST
where py && (goto :PYTHON_DOES_EXIST)
goto :PYTHON_DOES_NOT_EXIST
goto :EOF

:PYTHON_DOES_NOT_EXIST
echo.
echo ERROR: Python not found: please install it before!
echo.
pause
start "" "https://www.python.org/ftp/python/3.9.0/python-3.9.0-amd64.exe"
goto :EOF

:PYTHON_DOES_EXIST
py -m install -U robot-soccer-kit
py -m rsk.game_controller
