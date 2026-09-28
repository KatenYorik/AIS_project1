@echo off
chcp 65001 > nul
cd /d "%~dp0"
python split_help.py
echo.
echo Дальше:  python split_help.py --tools ^| --hint 1 ^| --check ^| --result
pause
