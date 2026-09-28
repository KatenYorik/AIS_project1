@echo off
chcp 65001 > nul
cd /d "%~dp0"
set LOG=log_obuchenie.txt
echo. >> %LOG%
echo ================ %date% %time% ================ >> %LOG%

echo [1/4] aug strong ...
python ..\step4_baseline_model\train.py --exp aug --aug strong >> %LOG% 2>&1

echo [2/4] frozen ...
python ..\step4_baseline_model\train.py --exp frozen >> %LOG% 2>&1

echo [3/4] сборка нечестного датасета ...
python ..\step2_dataset\prepare_data.py --seed 5 --random-split >> %LOG% 2>&1

echo [4/4] обучение на нечестном датасете ...
python ..\step4_baseline_model\train.py --exp small --frac 1.0 --data datasets\birds_v1_random --tag random >> %LOG% 2>&1

echo.
echo Готово. Весь вывод — в %LOG%, сводка по числам:
python ..\step5_metrics\svodka.py
pause
