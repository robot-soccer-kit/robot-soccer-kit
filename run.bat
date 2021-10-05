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
goto :EOF

:PYTHON_DOES_EXIST
py -m pip install pyserial numpy zmq pyqt5 pyqtwebengine opencv-python-headless opencv-contrib-python-headless
py -m ssl.app